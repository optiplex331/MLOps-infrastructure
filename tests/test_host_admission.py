from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mlops_infrastructure.host_admission import AdmissionError, sanitize
from mlops_infrastructure.schema import validate


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IMAGE = (
    "nvidia/cuda@sha256:"
    "8767a245ed2c481eb245d8f6c625accc3788e1fb8612403d6b4cd4645a4f09c7"
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class HostAdmissionTests(unittest.TestCase):
    def test_pending_contract_is_explicitly_not_evidence(self) -> None:
        template = load("contracts/host-admission/v1/pending-evidence.template.json")
        schema = load("contracts/host-admission/v1/evidence.schema.json")
        validate(template, schema)
        self.assertEqual(template["status"], "pending")
        self.assertFalse(template["synthetic"])
        self.assertTrue(all(gate["status"] == "pending" for gate in template["gates"]))
        self.assertIn("macOS", " ".join(template["limitations"]))

    def test_gpu_manifests_pin_image_and_request_exactly_one_gpu(self) -> None:
        for name in ("gpu-smoke", "gpu-capacity-holder", "gpu-capacity-contender"):
            pod = load(f"manifests/host-admission/{name}.pod.yaml")
            container = pod["spec"]["containers"][0]
            self.assertEqual(container["image"], EXPECTED_IMAGE)
            self.assertEqual(container["resources"]["requests"]["nvidia.com/gpu"], "1")
            self.assertEqual(container["resources"]["limits"]["nvidia.com/gpu"], "1")
            self.assertEqual(pod["spec"]["runtimeClassName"], "nvidia")
            self.assertEqual(pod["spec"]["nodeSelector"]["mlops.local/gpu"], "rtx-3080")

    def test_non_gpu_guard_has_no_gpu_request_or_toleration(self) -> None:
        pod = load("manifests/host-admission/non-gpu-guard.pod.yaml")
        rendered = json.dumps(pod, sort_keys=True)
        self.assertNotIn("nvidia.com/gpu", rendered)
        self.assertNotIn("tolerations", pod["spec"])

    def test_sanitizer_allowlist_drops_host_identity_and_credentials(self) -> None:
        raw = {
            "host": {
                "accessMethod": "ssh-lan",
                "architecture": "amd64",
                "cpuLogicalCores": 20,
                "cpuModel": "13th Gen Intel(R) Core(TM) i5-13600K",
                "filesystem": "ext4",
                "freeDiskBytes": 200_000_000_000,
                "hostname": "private-host",
                "kernel": "6.8.0",
                "operatingSystem": "Ubuntu",
                "operatingSystemVersion": "24.04",
                "ramBytes": 32_000_000_000,
                "sshKey": "private",
            },
            "gpu": {
                "cudaCompatibility": "12.8",
                "driverVersion": "570.00",
                "model": "NVIDIA GeForce RTX 3080",
                "powerWatts": 25.0,
                "serial": "private-serial",
                "temperatureC": 40.0,
                "vramMiB": 10240,
            },
            "runtime": {
                "containerRuntime": "27.0",
                "devicePluginReady": True,
                "k3s": "v1.32",
                "kubeconfig": "secret",
                "kubectlClient": "v1.32",
                "nvidiaToolkit": "1.17",
            },
            "cluster": {
                "allocatableGpu": 1,
                "containerGpuModel": "NVIDIA GeForce RTX 3080",
                "gpuLimit": 1,
                "gpuRequest": 1,
                "nodeLabel": True,
                "nodeTaint": True,
                "nonGpuOutcome": "untolerated_taint",
                "podExitCode": 0,
                "podGpuModel": "NVIDIA GeForce RTX 3080",
                "schedulingEventReasons": ["FailedScheduling"],
                "unavailableGpuOutcome": "insufficient_nvidia_com_gpu",
            },
            "measurements": {
                "idleDurationSeconds": 60,
                "idlePowerWatts": 25,
                "idleTemperatureC": 40,
                "smokeGpuMemoryUsedMiB": 512,
                "smokePowerWatts": 120,
                "smokeTemperatureC": 65,
            },
        }
        evidence = sanitize(
            raw,
            "a" * 40,
            "2026-07-23T00:00:00Z",
            load("config/host-admission-limits.v1.json"),
        )
        serialized = json.dumps(evidence)
        self.assertNotIn("private-host", serialized)
        self.assertNotIn("private-serial", serialized)
        self.assertNotIn("sshKey", serialized)
        self.assertNotIn("kubeconfig", serialized)
        self.assertEqual(evidence["status"], "passed")
        validate(evidence, load("contracts/host-admission/v1/evidence.schema.json"))

    def test_collector_rejects_current_macos_validation_host(self) -> None:
        if platform.system() != "Darwin":
            self.skipTest("this assertion is specific to the current validation host")
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "host-admission.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "bin/collect-host-admission",
                    "--access-method",
                    "local-console",
                    "--cluster-results",
                    "/nonexistent",
                    "--infrastructure-revision",
                    revision,
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_preflight_cannot_accept_non_linux(self) -> None:
        from mlops_infrastructure.host_admission import preflight

        with patch("platform.system", return_value="Darwin"):
            with self.assertRaisesRegex(AdmissionError, "native Linux"):
                preflight()


if __name__ == "__main__":
    unittest.main()
