"""CPU-only cross-repository synthetic rejection and evidence packaging."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from .canonical import canonical_json, load_canonical_json, sha256_bytes, sha256_file
from .schema import SchemaError, validate


CONTRACT_NAMES = (
    "release-request",
    "model-artifact",
    "release-decision",
    "model-release",
    "evidence-package",
)
REVISION = re.compile(r"^[0-9a-f]{40}$")
OUTPUT_NAMES = ("release-decision.json", "model-release.json", "evidence-package.json")


class ReleaseError(ValueError):
    pass


def _contained(path: Path, root: Path, description: str) -> Path:
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ReleaseError(f"{description} must be inside {root}") from exc
    return resolved


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"cannot load contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"contract must be a JSON object: {path}")
    return value


def _write(path: Path, value: Any) -> str:
    payload = canonical_json(value)
    path.write_bytes(payload)
    return sha256_bytes(payload)


def execute(
    *,
    project_repo: Path,
    request_path: Path,
    project_revision: str,
    infrastructure_revision: str,
    output_dir: Path,
    infrastructure_repo: Path,
) -> dict[str, str]:
    if project_repo.resolve() == infrastructure_repo.resolve():
        raise ReleaseError("Project and Infrastructure repositories must be distinct")
    if not REVISION.fullmatch(project_revision) or not REVISION.fullmatch(infrastructure_revision):
        raise ReleaseError("repository revisions must be lowercase 40-character Git object IDs")

    request_path = _contained(request_path, project_repo, "request")
    expected_request = project_repo.resolve(strict=True) / "fixtures" / "releases" / "rejected" / "release-request.json"
    if request_path != expected_request:
        raise ReleaseError(f"request must use the versioned rejected fixture: {expected_request}")
    contract_dir = project_repo.resolve(strict=True) / "contracts" / "v1"
    contract_paths = {name: contract_dir / f"{name}.schema.json" for name in CONTRACT_NAMES}
    missing = [str(path) for path in contract_paths.values() if not path.is_file()]
    if missing:
        raise ReleaseError(f"missing v1 contracts: {missing}")
    schemas = {name: _load_schema(path) for name, path in contract_paths.items()}

    try:
        request, request_bytes = load_canonical_json(request_path)
        validate(request, schemas["release-request"])
    except (OSError, ValueError, SchemaError) as exc:
        raise ReleaseError(str(exc)) from exc
    if request["projectRevision"] != project_revision:
        raise ReleaseError("project revision does not match ReleaseRequest")
    if request["infrastructureRevision"] != infrastructure_revision:
        raise ReleaseError("infrastructure revision does not match ReleaseRequest")
    if request["mode"] != "synthetic":
        raise ReleaseError("this entrypoint accepts synthetic requests only")

    artifact_path = request_path.parent / "model-artifact.json"
    artifact_path = _contained(artifact_path, project_repo, "model artifact fixture")
    try:
        artifact, artifact_bytes = load_canonical_json(artifact_path)
        validate(artifact, schemas["model-artifact"])
    except (OSError, ValueError, SchemaError) as exc:
        raise ReleaseError(str(exc)) from exc
    artifact_digest = sha256_bytes(artifact_bytes)
    if request["candidateArtifact"] != {
        "artifactId": artifact["artifactId"],
        "digest": artifact_digest,
    }:
        raise ReleaseError("candidate artifact ID or immutable document digest does not match request")
    if artifact["provenance"]["projectRevision"] != project_revision:
        raise ReleaseError("ModelArtifact provenance does not match project revision")

    configuration_path = _contained(
        request_path.parent / "release-configuration.json", project_repo, "release configuration fixture"
    )
    evaluation_path = _contained(
        request_path.parent / "evaluation-policy.json", project_repo, "evaluation policy fixture"
    )
    load_canonical_json(configuration_path)
    load_canonical_json(evaluation_path)
    configuration_digest = sha256_file(configuration_path)
    evaluation_digest = sha256_file(evaluation_path)
    if request["configurationDigest"] != configuration_digest:
        raise ReleaseError("release configuration immutable digest does not match request")
    if request["evaluationPolicyDigest"] != evaluation_digest:
        raise ReleaseError("evaluation policy immutable digest does not match request")

    payload_uri = artifact["payload"]["uri"]
    if payload_uri != "fixture://releases/rejected/adapter-payload.txt":
        raise ReleaseError("ModelArtifact payload URI is outside the versioned rejected fixture")
    payload_path = _contained(
        project_repo / "fixtures" / payload_uri.removeprefix("fixture://"),
        project_repo,
        "artifact payload fixture",
    )
    payload_bytes = payload_path.read_bytes()
    if len(payload_bytes) != artifact["payload"]["sizeBytes"]:
        raise ReleaseError("artifact payload size does not match ModelArtifact")
    if sha256_bytes(payload_bytes) != artifact["payload"]["digest"]:
        raise ReleaseError("artifact payload immutable digest does not match ModelArtifact")

    policy_path = infrastructure_repo / "config" / "synthetic-reject-policy.v1.json"
    policy, _ = load_canonical_json(policy_path)
    policy_digest = sha256_file(policy_path)
    if policy != {
        "decision": "rejected",
        "policy_id": "synthetic-reject/v1",
        "reason_code": "synthetic_fixture_forced_rejection",
        "schema_version": "v1",
    }:
        raise ReleaseError("synthetic rejection policy content is not recognized")

    request_id = request["requestId"]
    timestamp = request["requestedAt"]
    evidence_id = f"evidence.{request_id}"
    release_id = f"release.{request_id}.base"
    model_release = {
        "adapter": None,
        "deploymentConfigDigest": configuration_digest,
        "infrastructureRevision": infrastructure_revision,
        "model": artifact["baseModel"],
        "projectRevision": project_revision,
        "releaseId": release_id,
        "schemaVersion": "v1",
        "selectedAt": timestamp,
        "selection": "base",
        "synthetic": True,
    }
    validate(model_release, schemas["model-release"])
    model_release_digest = sha256_bytes(canonical_json(model_release))
    decision = {
        "candidateArtifact": {"digest": artifact_digest, "id": artifact["artifactId"]},
        "decidedAt": timestamp,
        "decisionId": f"decision.{request_id}",
        "evidencePackageId": evidence_id,
        "infrastructureRevision": infrastructure_revision,
        "outcome": "rejected",
        "projectRevision": project_revision,
        "reasonCodes": ["SYNTHETIC_FIXTURE_FORCED_REJECTION"],
        "requestId": request_id,
        "schemaVersion": "v1",
        "selectedRelease": {"digest": model_release_digest, "id": release_id},
        "synthetic": True,
    }
    validate(decision, schemas["release-decision"])
    decision_digest = sha256_bytes(canonical_json(decision))

    entries = [
        {"digest": sha256_bytes(request_bytes), "path": "project/fixtures/releases/rejected/release-request.json", "role": "fixture"},
        {"digest": artifact_digest, "path": "project/fixtures/releases/rejected/model-artifact.json", "role": "fixture"},
        {"digest": artifact["payload"]["digest"], "path": "project/fixtures/releases/rejected/adapter-payload.txt", "role": "fixture"},
        {"digest": configuration_digest, "path": "project/fixtures/releases/rejected/release-configuration.json", "role": "configuration"},
        {"digest": evaluation_digest, "path": "project/fixtures/releases/rejected/evaluation-policy.json", "role": "policy"},
        {"digest": policy_digest, "path": "infrastructure/config/synthetic-reject-policy.v1.json", "role": "policy"},
    ]
    for name in CONTRACT_NAMES:
        entries.append({
            "digest": sha256_file(contract_paths[name]),
            "path": f"project/contracts/v1/{name}.schema.json",
            "role": "configuration",
        })
    entries.extend(
        [
            {"digest": decision_digest, "path": "output/release-decision.json", "role": "decision"},
            {"digest": model_release_digest, "path": "output/model-release.json", "role": "release"},
        ]
    )
    evidence = {
        "entries": entries,
        "evidencePackageId": evidence_id,
        "generatedAt": timestamp,
        "infrastructureRevision": infrastructure_revision,
        "limitations": [
            "CPU-only synthetic contract execution; no GPU execution was performed.",
            "No Kubernetes cluster, workflow engine, model training, evaluation, serving, or publication was exercised.",
            "The result is not evidence of production readiness or model capability.",
        ],
        "modelReleaseDigest": model_release_digest,
        "projectRevision": project_revision,
        "releaseDecisionDigest": decision_digest,
        "requestId": request_id,
        "schemaVersion": "v1",
        "synthetic": True,
    }
    validate(evidence, schemas["evidence-package"])

    output_dir.mkdir(parents=True, exist_ok=True)
    unexpected = sorted(path.name for path in output_dir.iterdir())
    if unexpected:
        raise ReleaseError(f"output directory must be empty: {unexpected}")
    digests = {
        "release-decision.json": _write(output_dir / "release-decision.json", decision),
        "model-release.json": _write(output_dir / "model-release.json", model_release),
        "evidence-package.json": _write(output_dir / "evidence-package.json", evidence),
    }
    manifest = "".join(f"{digest.removeprefix('sha256:')}  {name}\n" for name, digest in sorted(digests.items()))
    (output_dir / "manifest.sha256").write_text(manifest, encoding="ascii")
    return digests


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-repo", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--project-revision", required=True)
    parser.add_argument("--infrastructure-revision", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    infrastructure_repo = Path(__file__).resolve().parents[2]
    try:
        digests = execute(
            project_repo=args.project_repo,
            request_path=args.request,
            project_revision=args.project_revision,
            infrastructure_revision=args.infrastructure_revision,
            output_dir=args.output_dir,
            infrastructure_repo=infrastructure_repo,
        )
    except (OSError, ReleaseError, SchemaError, KeyError) as exc:
        print(f"synthetic release rejected before decision: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"outcome": "rejected", "outputs": digests}, sort_keys=True))
    return 0
