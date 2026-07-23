from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def document(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def container(resource: dict) -> dict:
    return resource["spec"]["template"]["spec"]["containers"][0]


class Ticket04PlatformManifestTests(unittest.TestCase):
    def test_kustomizations_render_without_network_or_cluster(self) -> None:
        for relative in ("platform/argo", "platform/mlflow", "platform/minio", "workflows"):
            result = subprocess.run(
                ["kubectl", "kustomize", str(ROOT / relative)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("app.kubernetes.io/part-of: mlops-release-lab", result.stdout)

    def test_stateful_platform_modules_are_bounded_lab_services(self) -> None:
        mlflow = document("platform/mlflow/deployment.json")
        minio = document("platform/minio/statefulset.json")
        for resource in (mlflow, minio):
            pod = resource["spec"]["template"]["spec"]
            workload = container(resource)
            self.assertEqual(resource["metadata"]["namespace"], "mlops-lab")
            self.assertEqual(resource["metadata"]["annotations"]["mlops-lab/persistence-scope"], "lab-only")
            self.assertFalse(pod["automountServiceAccountToken"])
            self.assertIn("requests", workload["resources"])
            self.assertIn("limits", workload["resources"])
            self.assertIn("startupProbe", workload)
            self.assertIn("readinessProbe", workload)
            self.assertIn("livenessProbe", workload)
            self.assertNotIn(":latest", workload["image"])
        self.assertEqual(mlflow["spec"]["strategy"]["type"], "Recreate")
        self.assertEqual(mlflow["spec"]["replicas"], 1)
        self.assertEqual(minio["spec"]["replicas"], 1)
        self.assertEqual(minio["spec"]["updateStrategy"]["type"], "OnDelete")
        self.assertEqual(minio["spec"]["volumeClaimTemplates"][0]["spec"]["storageClassName"], "local-path")

    def test_platform_uses_referenced_secrets_and_namespace_roles_only(self) -> None:
        tracked = list((ROOT / "platform").rglob("*.json")) + list((ROOT / "workflows").rglob("*.json"))
        resources = [document(str(path.relative_to(ROOT))) for path in tracked]
        kinds = [resource["kind"] for resource in resources if "kind" in resource]
        self.assertNotIn("Secret", kinds)
        self.assertNotIn("ClusterRole", kinds)
        self.assertNotIn("ClusterRoleBinding", kinds)
        for relative in (
            "platform/argo/controller-role.json",
            "platform/argo/controller-rolebinding.json",
            "workflows/workflow-role.json",
            "workflows/workflow-rolebinding.json",
        ):
            self.assertEqual(document(relative)["metadata"]["namespace"], "mlops-lab")

    def test_workflow_interface_is_explicit_bounded_and_fail_closed(self) -> None:
        workflow = document("workflows/cpu-synthetic-release-v1.json")
        spec = workflow["spec"]
        self.assertEqual(workflow["apiVersion"], "argoproj.io/v1alpha1")
        self.assertEqual(workflow["kind"], "WorkflowTemplate")
        self.assertEqual(spec["entrypoint"], "release")
        self.assertEqual(spec["onExit"], "finalize-execution")
        self.assertEqual(spec["activeDeadlineSeconds"], 900)
        self.assertEqual(spec["podGC"]["strategy"], "OnWorkflowCompletion")
        parameters = {item["name"]: item for item in spec["arguments"]["parameters"]}
        required = {
            "schema-version", "request-id", "requested-at", "project-revision",
            "infrastructure-revision", "request-digest", "configuration-digest",
            "fixture-digest", "evaluation-policy-digest", "candidate-artifact-id",
            "candidate-artifact-digest", "base-model-id", "base-model-digest",
            "mlflow-endpoint", "minio-endpoint", "inject-failure",
        }
        self.assertEqual(set(parameters), required)
        self.assertEqual(parameters["schema-version"]["value"], "v1")
        templates = {item["name"]: item for item in spec["templates"]}
        dag = templates["release"]["dag"]["tasks"]
        tasks = {item["name"]: item for item in dag}
        self.assertEqual(
            set(tasks),
            {"dependency-preflight", "start-run", "build-content", "stage-artifacts", "finish-run", "promote"},
        )
        self.assertEqual(tasks["promote"]["depends"], "finish-run.Succeeded")
        for name in ("dependency-preflight", "start-run", "build-content", "stage-artifacts", "finish-run", "promote"):
            template = templates[tasks[name]["template"]]
            self.assertIn("retryStrategy", template)
            self.assertIn("activeDeadlineSeconds", template)
        build_outputs = templates["build-content"]["outputs"]
        self.assertGreaterEqual(len(build_outputs["artifacts"]), 4)
        self.assertTrue(all("path" in artifact for artifact in build_outputs["artifacts"]))
        rendered = json.dumps(workflow)
        self.assertNotIn("emptyDir", rendered)
        self.assertIn("{{workflow.uid}}", rendered)
        self.assertIn("{{workflow.status}}", rendered)


if __name__ == "__main__":
    unittest.main()
