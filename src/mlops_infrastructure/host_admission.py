"""Native-Ubuntu host admission collection and allowlist sanitization."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from typing import Any

from .canonical import canonical_json
from .schema import validate


REQUIRED_COMMANDS = (
    "findmnt",
    "k3s",
    "kubectl",
    "nvidia-ctk",
    "nvidia-smi",
    "systemctl",
)
REVISION = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_GPU = "NVIDIA GeForce RTX 3080"
SANITIZED_OBSERVATION_FIELDS = {
    "gpu": (
        "cudaCompatibility",
        "driverVersion",
        "model",
        "powerWatts",
        "temperatureC",
        "vramMiB",
    ),
    "host": (
        "accessMethod",
        "architecture",
        "cpuLogicalCores",
        "cpuModel",
        "filesystem",
        "freeDiskBytes",
        "kernel",
        "operatingSystem",
        "operatingSystemVersion",
        "ramBytes",
    ),
    "runtime": (
        "containerRuntime",
        "devicePluginReady",
        "k3s",
        "kubectlClient",
        "nvidiaToolkit",
    ),
    "cluster": (
        "allocatableGpu",
        "containerGpuModel",
        "gpuLimit",
        "gpuRequest",
        "nodeLabel",
        "nodeTaint",
        "nonGpuOutcome",
        "podExitCode",
        "podGpuModel",
        "schedulingEventReasons",
        "unavailableGpuOutcome",
    ),
    "measurements": (
        "idleDurationSeconds",
        "idlePowerWatts",
        "idleTemperatureC",
        "smokeGpuMemoryUsedMiB",
        "smokePowerWatts",
        "smokeTemperatureC",
    ),
}
GATE_OBSERVATION_SECTIONS = {
    "native_ubuntu_host": "host",
    "container_gpu_identity": "cluster",
    "scheduled_pod_gpu_identity": "cluster",
    "node_gpu_policy": "cluster",
    "bounded_scheduling_guards": "cluster",
    "idle_and_smoke_limits": "measurements",
}


class AdmissionError(ValueError):
    pass


def _run(*command: str) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AdmissionError(f"command failed ({' '.join(command)}): {result.stderr.strip()}")
    return result.stdout.strip()


def _ubuntu_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def preflight() -> dict[str, str]:
    if platform.system() != "Linux":
        raise AdmissionError("host admission must run on native Linux")
    release = _ubuntu_release()
    if release.get("ID") != "ubuntu":
        raise AdmissionError("host admission target must be native Ubuntu")
    if platform.machine() not in {"x86_64", "amd64"}:
        raise AdmissionError("host admission target must be amd64")
    missing = [name for name in REQUIRED_COMMANDS if shutil.which(name) is None]
    if missing:
        raise AdmissionError(f"missing required host commands: {missing}")
    return {
        "operatingSystem": release.get("NAME", "Ubuntu"),
        "operatingSystemVersion": release.get("VERSION_ID", "unknown"),
    }


def _read_cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    raise AdmissionError("CPU model is unavailable")


def _read_ram_bytes() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    raise AdmissionError("RAM total is unavailable")


def _version(command: tuple[str, ...]) -> str:
    output = _run(*command)
    return output.splitlines()[0][:200]


def collect_host(access_method: str) -> dict[str, Any]:
    release = preflight()
    gpu_fields = _run(
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ).splitlines()
    if len(gpu_fields) != 1:
        raise AdmissionError("exactly one visible GPU is required")
    fields = [field.strip() for field in gpu_fields[0].split(",")]
    if len(fields) != 5:
        raise AdmissionError("unexpected nvidia-smi query output")
    nvidia_summary = _run("nvidia-smi")
    cuda_match = re.search(r"CUDA Version:\s*([0-9.]+)", nvidia_summary)
    if cuda_match is None:
        raise AdmissionError("CUDA compatibility is unavailable from nvidia-smi")
    root_disk = shutil.disk_usage("/")
    return {
        "host": {
            "accessMethod": access_method,
            "architecture": "amd64",
            "cpuLogicalCores": os.cpu_count(),
            "cpuModel": _read_cpu_model(),
            "filesystem": _run("findmnt", "-n", "-o", "FSTYPE", "/"),
            "freeDiskBytes": root_disk.free,
            "kernel": platform.release(),
            "operatingSystem": release["operatingSystem"],
            "operatingSystemVersion": release["operatingSystemVersion"],
            "ramBytes": _read_ram_bytes(),
        },
        "gpu": {
            "cudaCompatibility": cuda_match.group(1),
            "driverVersion": fields[2],
            "model": fields[0],
            "powerWatts": float(fields[4]),
            "temperatureC": float(fields[3]),
            "vramMiB": int(fields[1]),
        },
        "runtime": {
            "containerRuntime": _version(("k3s", "ctr", "version")),
            "k3s": _version(("k3s", "--version")),
            "kubectlClient": _version(("kubectl", "version", "--client")),
            "nvidiaToolkit": _version(("nvidia-ctk", "--version")),
        },
    }


def sanitize(raw: dict[str, Any], revision: str, collected_at: str, limits: dict[str, Any]) -> dict[str, Any]:
    """Copy only reviewable fields; identity, serial, network and credentials drop out."""
    host = raw["host"]
    cluster = raw["cluster"]
    measurements = raw["measurements"]
    observations = {
        section: {key: raw[section][key] for key in fields}
        for section, fields in SANITIZED_OBSERVATION_FIELDS.items()
    }
    checks = {
        "native_ubuntu_host": host["operatingSystem"].lower().startswith("ubuntu") and host["architecture"] == "amd64",
        "container_gpu_identity": cluster["containerGpuModel"] == EXPECTED_GPU,
        "scheduled_pod_gpu_identity": cluster["podGpuModel"] == EXPECTED_GPU and cluster["podExitCode"] == 0,
        "node_gpu_policy": cluster["nodeLabel"] and cluster["nodeTaint"] and cluster["allocatableGpu"] == 1 and cluster["gpuRequest"] == 1 and cluster["gpuLimit"] == 1,
        "bounded_scheduling_guards": cluster["nonGpuOutcome"] == "untolerated_taint" and cluster["unavailableGpuOutcome"] == "insufficient_nvidia_com_gpu",
        "idle_and_smoke_limits": (
            measurements["idleDurationSeconds"] >= limits["idleSampleSeconds"]
            and host["freeDiskBytes"] >= limits["minimumFreeDiskBytes"]
            and measurements["idleTemperatureC"] <= limits["maximumGpuTemperatureC"]
            and measurements["smokeTemperatureC"] <= limits["maximumGpuTemperatureC"]
            and measurements["idlePowerWatts"] <= limits["maximumGpuPowerWatts"]
            and measurements["smokePowerWatts"] <= limits["maximumGpuPowerWatts"]
            and measurements["smokeGpuMemoryUsedMiB"] <= limits["maximumGpuMemoryUsedMiB"]
        ),
    }
    gates = [
        {
            "evidence": [f"observations/{GATE_OBSERVATION_SECTIONS[name]}"],
            "gate": name,
            "status": "passed" if passed else "failed",
        }
        for name, passed in checks.items()
    ]
    return {
        "admissionId": "local-k3s-gpu-runtime-v1",
        "collectedAt": collected_at,
        "gates": gates,
        "infrastructureRevision": revision,
        "limitations": [
            "Single-node, one-GPU local lab evidence; no high availability, autoscaling, or production reliability claim.",
            "Measurements describe one bounded admission execution only.",
        ],
        "observations": observations,
        "schemaVersion": "v1",
        "status": "passed" if all(checks.values()) else "failed",
        "synthetic": False,
        "target": {
            "architecture": "amd64",
            "gpuCount": 1,
            "gpuModel": EXPECTED_GPU,
            "nodeCount": 1,
            "operatingSystem": "Ubuntu",
            "runtime": "native",
        },
    }


def _verify_revision(repository: Path, revision: str) -> None:
    if REVISION.fullmatch(revision) is None:
        raise AdmissionError("infrastructure revision must be a lowercase 40-character Git object ID")
    head = _run("git", "-C", str(repository), "rev-parse", "--verify", "HEAD")
    _run("git", "-C", str(repository), "cat-file", "-e", f"{revision}^{{commit}}")
    if head != revision:
        raise AdmissionError("infrastructure revision must equal current HEAD")
    if _run("git", "-C", str(repository), "status", "--porcelain", "--untracked-files=normal"):
        raise AdmissionError("Infrastructure Repository worktree must be clean")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-method", choices=("local-console", "ssh-lan"), required=True)
    parser.add_argument("--cluster-results", required=True, type=Path)
    parser.add_argument("--infrastructure-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    try:
        _verify_revision(repository, args.infrastructure_revision)
        if args.output.resolve(strict=False).is_relative_to(repository.resolve()):
            raise AdmissionError("sanitized evidence output must be outside the repository")
        raw = collect_host(args.access_method)
        cluster_results = json.loads(args.cluster_results.read_text(encoding="utf-8"))
        raw["cluster"] = cluster_results["cluster"]
        raw["measurements"] = cluster_results["measurements"]
        raw["runtime"].update(cluster_results["runtime"])
        limits = json.loads((repository / "config" / "host-admission-limits.v1.json").read_text(encoding="utf-8"))
        collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        evidence = sanitize(raw, args.infrastructure_revision, collected_at, limits)
        schema = json.loads(
            (
                repository
                / "contracts"
                / "host-admission"
                / "v1"
                / "evidence.schema.json"
            ).read_text(encoding="utf-8")
        )
        validate(evidence, schema)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_json(evidence))
    except (AdmissionError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"host admission failed: {exc}", file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
