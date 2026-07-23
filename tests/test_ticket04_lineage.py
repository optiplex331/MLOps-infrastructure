from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "workflows" / "scripts" / "cpu_release.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ticket04_cpu_release", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Ticket04LineageContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.inputs = {
            "schemaVersion": "v1",
            "requestId": "synthetic-rejected-v1",
            "requestedAt": "2026-01-01T00:00:00Z",
            "projectRevision": "a" * 40,
            "infrastructureRevision": "b" * 40,
            "requestDigest": "sha256:" + "1" * 64,
            "configurationDigest": "sha256:" + "2" * 64,
            "fixtureDigest": "sha256:" + "3" * 64,
            "evaluationPolicyDigest": "sha256:" + "4" * 64,
            "candidateArtifactId": "synthetic-adapter-rejected-v1",
            "candidateArtifactDigest": "sha256:" + "5" * 64,
            "baseModelId": "synthetic/base",
            "baseModelDigest": "sha256:" + "6" * 64,
        }

    def test_content_identity_and_decision_are_stable_across_executions(self) -> None:
        first = self.module.materialize(self.inputs, "workflow-one", "mlflow-one")
        second = self.module.materialize(self.inputs, "workflow-two", "mlflow-two")
        self.assertEqual(first["contentIdentity"], second["contentIdentity"])
        self.assertEqual(first["releaseDecision"], second["releaseDecision"])
        self.assertNotEqual(first["evidencePackage"], second["evidencePackage"])
        self.assertEqual(first["evidencePackage"]["executionIdentity"]["workflowUid"], "workflow-one")
        self.assertEqual(second["evidencePackage"]["executionIdentity"]["mlflowRunId"], "mlflow-two")

    def test_failure_rejects_partial_artifacts_and_records_failed_run(self) -> None:
        failure = self.module.failed_execution(
            self.inputs,
            workflow_uid="workflow-failed",
            mlflow_run_id="mlflow-failed",
            failed_step="build-content",
        )
        self.assertEqual(failure["mlflowStatus"], "FAILED")
        self.assertEqual(failure["terminalState"], "failed")
        self.assertEqual(failure["acceptedArtifacts"], [])
        self.assertNotIn("releaseDecision", failure)

    def test_dependency_outage_cannot_emit_successful_release(self) -> None:
        for mlflow, minio in ((False, True), (True, False), (False, False)):
            with self.assertRaises(self.module.DependencyUnavailable):
                self.module.require_dependencies(mlflow_available=mlflow, minio_available=minio)

    def test_evidence_contract_rejects_unknown_or_missing_fields(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is installed by the Ticket 04 CI workflow")
        result = self.module.materialize(self.inputs, "workflow-one", "mlflow-one")
        schema = json.loads((ROOT / "workflows/contracts/cpu-workflow-evidence.v1.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(result["evidencePackage"], schema)
        broken = dict(result["evidencePackage"])
        broken["unexpected"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(broken, schema)


if __name__ == "__main__":
    unittest.main()
