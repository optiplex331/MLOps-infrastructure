from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryBoundaryTests(unittest.TestCase):
    def test_repository_is_independent(self) -> None:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(Path(top), ROOT)

    def test_sensitive_and_runtime_paths_are_ignored(self) -> None:
        dangerous = [
            ".env",
            "credentials.json",
            "config/credentials.json",
            "secrets/token.txt",
            "nested/secrets/cloud-credentials.json",
            "cluster.kubeconfig",
            "rendered-secrets/app.yaml",
            "tracking-data/1/meta.yaml",
            "object-store-data/bucket/object",
            "model-cache/weights.safetensors",
            "raw-data/scenarios.jsonl",
            "raw-evaluation/targets.jsonl",
            "evidence/local-host.json",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=ROOT,
            input="\n".join(dangerous) + "\n",
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.splitlines(), dangerous)

    def test_only_the_phase_one_platform_surface_remains(self) -> None:
        self.assertTrue((ROOT / "charts" / "llm-inference" / "Chart.yaml").is_file())
        for removed in (
            "bin/run-synthetic-release",
            "config/synthetic-reject-policy.v1.json",
            "src/mlops_infrastructure/synthetic_release.py",
        ):
            self.assertFalse((ROOT / removed).exists(), removed)
        self.assertFalse(any(path.is_file() for path in (ROOT / "platform").rglob("*")))
        self.assertFalse(any(path.is_file() for path in (ROOT / "workflows").rglob("*")))

    def test_license_is_present(self) -> None:
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_publishable_files_do_not_contain_representative_secrets(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        patterns = (
            re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            re.compile(rb"(?i)(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"][^'\"]{8,}"),
        )
        violations = []
        for relative in result.stdout.splitlines():
            path = ROOT / relative
            if not path.is_file():
                continue
            payload = path.read_bytes()
            if any(pattern.search(payload) for pattern in patterns):
                violations.append(relative)
        self.assertEqual(violations, [])



if __name__ == "__main__":
    unittest.main()
