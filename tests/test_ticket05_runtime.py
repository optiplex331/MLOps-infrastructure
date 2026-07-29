from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from mlops_infrastructure.schema import validate


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class Ticket05RuntimeTests(unittest.TestCase):
    def test_profile_pins_one_runtime_shape(self) -> None:
        profile = load("config/runtime-admission-profile.v1.json")
        limits = load("config/host-admission-limits.v1.json")
        self.assertEqual(profile["k3s"]["version"], "v1.32.6+k3s1")
        self.assertEqual(profile["k3s"]["containerRuntime"], "embedded-containerd")
        self.assertEqual(profile["k3s"]["retainedComponents"], ["local-path", "metrics-server"])
        self.assertEqual(profile["k3s"]["disabledComponents"], ["traefik", "servicelb"])
        self.assertEqual(profile["host"]["gpuCount"], 1)
        self.assertEqual(profile["host"]["gpuModel"], "NVIDIA GeForce RTX 3080")
        self.assertEqual(limits["minimumFreeDiskBytes"], 50 * 1024**3)

    def test_k3s_installation_keeps_required_addons_and_disables_only_network_addons(self) -> None:
        installer = (ROOT / "runtime/k3s/install-single-node.sh").read_text(encoding="utf-8")
        self.assertIn('INSTALL_K3S_VERSION="$K3S_VERSION"', installer)
        self.assertIn("- traefik", installer)
        self.assertIn("- servicelb", installer)
        self.assertNotIn("local-path", installer)
        self.assertNotIn("metrics-server", installer)
        self.assertRegex(installer, r"K3S_VERSION='v1\.32\.6\+k3s1'")

    def test_smoke_workload_is_namespace_scoped_and_requests_one_gpu(self) -> None:
        manifest = (ROOT / "manifests/runtime-admission/gpu-smoke.pod.yaml").read_text(encoding="utf-8")
        self.assertIn("namespace: mlops-runtime-admission", manifest)
        self.assertIn("runtimeClassName: nvidia", manifest)
        self.assertEqual(manifest.count('nvidia.com/gpu: "1"'), 2)
        self.assertIn("image: nvidia/cuda@sha256:", manifest)
        self.assertNotRegex(manifest, r"(?:kubeconfig|credentials|/etc/rancher/k3s)")

    def test_device_plugin_manifest_and_values_are_pinned(self) -> None:
        manifest = (ROOT / "manifests/runtime-admission/nvidia-device-plugin.yaml").read_text(encoding="utf-8")
        values = (ROOT / "runtime/nvidia/device-plugin-values.yaml").read_text(encoding="utf-8")
        self.assertIn("kind: RuntimeClass", manifest)
        self.assertIn("handler: nvidia", manifest)
        self.assertIn("version: 0.17.1", manifest)
        self.assertIn("failOnInitError: true", manifest)
        self.assertIn("runtimeClassName: nvidia", values)
        self.assertIn("name: nvidia-device-plugin-config", values)
        self.assertIn("affinity: null", values)
        self.assertIn("key: mlops.local/gpu", values)
        self.assertIn("effect: NoSchedule", values)
        self.assertIn("affinity: null", manifest)
        self.assertIn("key: mlops.local/gpu", manifest)
        self.assertNotIn(":latest", manifest + values)

    def test_pending_evidence_is_sanitized_and_validates(self) -> None:
        evidence = load("contracts/runtime-admission/v1/pending-evidence.template.json")
        schema = load("contracts/runtime-admission/v1/evidence.schema.json")
        validate(evidence, schema)
        self.assertEqual(evidence["status"], "pending")
        self.assertTrue(evidence["sensitiveFieldsExcluded"])
        self.assertEqual(evidence["limitsReference"], "config/host-admission-limits.v1.json")
        self.assertEqual(len(evidence["checks"]), 8)
        self.assertTrue(all(check["action"] for check in evidence["checks"]))


if __name__ == "__main__":
    unittest.main()
