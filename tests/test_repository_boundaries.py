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
            "secrets/token.txt",
            "cluster.kubeconfig",
            "rendered-secrets/app.yaml",
            "mlruns/1/meta.yaml",
            "minio-data/bucket/object",
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

    def test_ticket_one_contains_no_platform_or_model_artifacts(self) -> None:
        forbidden_suffixes = {".kubeconfig", ".pem", ".key", ".safetensors", ".pt"}
        files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]
        self.assertFalse([path for path in files if path.suffix in forbidden_suffixes])
        self.assertFalse([path for path in files if path.name == "Chart.yaml"])

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
