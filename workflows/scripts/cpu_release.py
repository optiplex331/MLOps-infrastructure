#!/usr/bin/env python3
"""Pure CPU workflow contract helpers used by the Argo synthetic release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class DependencyUnavailable(RuntimeError):
    """Raised before work when required lineage or artifact services are absent."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value)
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def require_dependencies(*, mlflow_available: bool, minio_available: bool) -> None:
    missing = []
    if not mlflow_available:
        missing.append("MLflow")
    if not minio_available:
        missing.append("MinIO")
    if missing:
        raise DependencyUnavailable(f"required workflow dependencies unavailable: {', '.join(missing)}")


def content_identity(inputs: dict[str, Any]) -> dict[str, Any]:
    immutable = {
        key: inputs[key]
        for key in (
            "schemaVersion",
            "requestId",
            "requestedAt",
            "projectRevision",
            "infrastructureRevision",
            "requestDigest",
            "configurationDigest",
            "fixtureDigest",
            "evaluationPolicyDigest",
            "candidateArtifactId",
            "candidateArtifactDigest",
            "baseModelId",
            "baseModelDigest",
        )
    }
    return {"digest": sha256(immutable), "inputs": immutable}


def materialize(
    inputs: dict[str, Any], workflow_uid: str, mlflow_run_id: str
) -> dict[str, Any]:
    identity = content_identity(inputs)
    decision = {
        "contentIdentityDigest": identity["digest"],
        "failedClauses": ["synthetic_fixture_forces_rejection"],
        "outcome": "rejected",
        "schemaVersion": "v1",
        "selectedArtifactDigest": inputs["baseModelDigest"],
        "selectedModelId": inputs["baseModelId"],
    }
    evidence = {
        "contentIdentity": identity,
        "decisionDigest": sha256(decision),
        "executionIdentity": {
            "mlflowRunId": mlflow_run_id,
            "workflowUid": workflow_uid,
        },
        "lineage": {
            "infrastructureRevision": inputs["infrastructureRevision"],
            "minioObjects": [
                {
                    "digest": inputs["candidateArtifactDigest"],
                    "key": f"sha256/{inputs['candidateArtifactDigest'].removeprefix('sha256:')}",
                }
            ],
            "projectRevision": inputs["projectRevision"],
        },
        "limitations": [
            "CPU-only synthetic rejected workflow; no GPU, model-training, or production capability evidence."
        ],
        "schemaVersion": "v1",
        "terminalState": "rejected",
    }
    return {
        "contentIdentity": identity,
        "evidencePackage": evidence,
        "releaseDecision": decision,
    }


def failed_execution(
    inputs: dict[str, Any],
    *,
    workflow_uid: str,
    mlflow_run_id: str,
    failed_step: str,
) -> dict[str, Any]:
    return {
        "acceptedArtifacts": [],
        "contentIdentity": content_identity(inputs),
        "executionIdentity": {
            "mlflowRunId": mlflow_run_id,
            "workflowUid": workflow_uid,
        },
        "failedStep": failed_step,
        "mlflowStatus": "FAILED",
        "schemaVersion": "v1",
        "terminalState": "failed",
    }


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("materialize", "fail"))
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--workflow-uid", required=True)
    parser.add_argument("--mlflow-run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--failed-step")
    args = parser.parse_args()
    inputs = _load(args.inputs)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    if args.command == "materialize":
        result = materialize(inputs, args.workflow_uid, args.mlflow_run_id)
        for key, filename in (
            ("contentIdentity", "content-identity.json"),
            ("releaseDecision", "release-decision.json"),
            ("evidencePackage", "evidence-package.json"),
        ):
            (args.output_dir / filename).write_bytes(canonical(result[key]))
    else:
        if not args.failed_step:
            parser.error("--failed-step is required for fail")
        result = failed_execution(
            inputs,
            workflow_uid=args.workflow_uid,
            mlflow_run_id=args.mlflow_run_id,
            failed_step=args.failed_step,
        )
        (args.output_dir / "failed-execution.json").write_bytes(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
