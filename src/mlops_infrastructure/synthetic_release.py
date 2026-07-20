"""CPU-only cross-repository synthetic rejection and evidence packaging."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
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
PROJECT_REVISION_TOKEN = "${PROJECT_REVISION}"
INFRASTRUCTURE_REVISION_TOKEN = "${INFRASTRUCTURE_REVISION}"
MODEL_ARTIFACT_DIGEST_TOKEN = "${MODEL_ARTIFACT_DIGEST}"


class ReleaseError(ValueError):
    pass


def _contained(path: Path, root: Path, description: str) -> Path:
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ReleaseError(f"{description} must be inside {root}") from exc
    return resolved


def _outside_repositories(path: Path, repositories: tuple[Path, ...]) -> None:
    resolved = path.resolve(strict=False)
    for repository in repositories:
        try:
            resolved.relative_to(repository.resolve(strict=True))
        except ValueError:
            continue
        raise ReleaseError(f"output directory must be outside both repositories: {resolved}")


def _load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"cannot load contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"contract must be a JSON object: {path}")
    return value


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseError(f"git {' '.join(arguments)} failed for {repo}: {detail}")
    return result.stdout.strip()


def _verify_clean_head(repo: Path, supplied_revision: str, label: str) -> None:
    if not (repo / ".git").exists():
        raise ReleaseError(f"{label} Repository is not an independent Git worktree: {repo}")
    _git(repo, "cat-file", "-e", f"{supplied_revision}^{{commit}}")
    head = _git(repo, "rev-parse", "--verify", "HEAD")
    if supplied_revision != head:
        raise ReleaseError(f"{label} revision must equal current HEAD ({head})")
    dirty = _git(repo, "status", "--porcelain", "--untracked-files=normal")
    if dirty:
        raise ReleaseError(f"{label} Repository worktree must be clean")


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
    _verify_clean_head(project_repo, project_revision, "Project")
    _verify_clean_head(infrastructure_repo, infrastructure_revision, "Infrastructure")
    _outside_repositories(output_dir, (project_repo, infrastructure_repo))

    request_path = _contained(request_path, project_repo, "request")
    expected_request = project_repo.resolve(strict=True) / "fixtures" / "releases" / "rejected" / "release-request.template.json"
    if request_path != expected_request:
        raise ReleaseError(f"request must use the versioned rejected fixture: {expected_request}")
    contract_dir = project_repo.resolve(strict=True) / "contracts" / "v1"
    contract_paths = {name: contract_dir / f"{name}.schema.json" for name in CONTRACT_NAMES}
    missing = [str(path) for path in contract_paths.values() if not path.is_file()]
    if missing:
        raise ReleaseError(f"missing v1 contracts: {missing}")
    schemas = {name: _load_schema(path) for name, path in contract_paths.items()}

    try:
        request_template, request_template_bytes = load_canonical_json(request_path)
    except (OSError, ValueError, SchemaError) as exc:
        raise ReleaseError(str(exc)) from exc
    if request_template.get("projectRevision") != PROJECT_REVISION_TOKEN:
        raise ReleaseError("ReleaseRequest template has an unknown project revision placeholder")
    if request_template.get("infrastructureRevision") != INFRASTRUCTURE_REVISION_TOKEN:
        raise ReleaseError("ReleaseRequest template has an unknown infrastructure revision placeholder")
    if request_template.get("mode") != "synthetic":
        raise ReleaseError("this entrypoint accepts synthetic requests only")

    artifact_path = request_path.parent / "model-artifact.template.json"
    artifact_path = _contained(artifact_path, project_repo, "model artifact fixture")
    try:
        artifact_template, artifact_template_bytes = load_canonical_json(artifact_path)
    except (OSError, ValueError, SchemaError) as exc:
        raise ReleaseError(str(exc)) from exc
    if request_template.get("candidateArtifact") != {
        "artifactId": artifact_template.get("artifactId"),
        "digest": MODEL_ARTIFACT_DIGEST_TOKEN,
    }:
        raise ReleaseError("ReleaseRequest template has an unknown model artifact digest placeholder")
    artifact_template_digest = sha256_bytes(artifact_template_bytes)
    if artifact_template.get("provenance", {}).get("projectRevision") != PROJECT_REVISION_TOKEN:
        raise ReleaseError("ModelArtifact template has an unknown project revision placeholder")

    artifact = copy.deepcopy(artifact_template)
    artifact["provenance"]["projectRevision"] = project_revision
    artifact_bytes = canonical_json(artifact)
    validate(artifact, schemas["model-artifact"])
    artifact_digest = sha256_bytes(artifact_bytes)

    request = copy.deepcopy(request_template)
    request["projectRevision"] = project_revision
    request["infrastructureRevision"] = infrastructure_revision
    request["candidateArtifact"]["digest"] = artifact_digest
    request_bytes = canonical_json(request)
    validate(request, schemas["release-request"])

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
    if request_template["configurationDigest"] != configuration_digest:
        raise ReleaseError("release configuration immutable digest does not match request")
    if request_template["evaluationPolicyDigest"] != evaluation_digest:
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

    closure_fixtures = {
        "base-model.manifest.json": artifact["baseModel"]["digest"],
        "source-records.json": artifact["provenance"]["sourceDigest"],
        "tokenizer.manifest.json": artifact["tokenizer"]["digest"],
    }
    closure_paths: dict[str, Path] = {}
    for filename, expected_digest in closure_fixtures.items():
        closure_path = _contained(request_path.parent / filename, project_repo, filename)
        load_canonical_json(closure_path)
        if sha256_file(closure_path) != expected_digest:
            raise ReleaseError(f"{filename} immutable digest does not match ModelArtifact")
        closure_paths[filename] = closure_path

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
        {"digest": sha256_bytes(request_template_bytes), "path": "project/fixtures/releases/rejected/release-request.template.json", "role": "fixture"},
        {"digest": artifact_template_digest, "path": "project/fixtures/releases/rejected/model-artifact.template.json", "role": "fixture"},
        {"digest": artifact["payload"]["digest"], "path": "project/fixtures/releases/rejected/adapter-payload.txt", "role": "fixture"},
        {"digest": configuration_digest, "path": "project/fixtures/releases/rejected/release-configuration.json", "role": "configuration"},
        {"digest": evaluation_digest, "path": "project/fixtures/releases/rejected/evaluation-policy.json", "role": "policy"},
        {"digest": policy_digest, "path": "infrastructure/config/synthetic-reject-policy.v1.json", "role": "policy"},
    ]
    for filename in sorted(closure_paths):
        entries.append({
            "digest": sha256_file(closure_paths[filename]),
            "path": f"project/fixtures/releases/rejected/{filename}",
            "role": "fixture",
        })
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
            {"digest": sha256_bytes(request_bytes), "path": "output/release-request.json", "role": "output"},
            {"digest": artifact_digest, "path": "output/model-artifact.json", "role": "output"},
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
        "release-request.json": _write(output_dir / "release-request.json", request),
        "model-artifact.json": _write(output_dir / "model-artifact.json", artifact),
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
