from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("MLOPS_PROJECT_REPO", ROOT.parent / "MLOps"))
REQUEST_RELATIVE = Path("fixtures/releases/rejected/release-request.json")
PROJECT_REVISION = "1" * 40
INFRASTRUCTURE_REVISION = "2" * 40


def run_release(project: Path, output: Path, *, project_revision: str = PROJECT_REVISION) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(ROOT / "bin" / "run-synthetic-release"),
            "--project-repo",
            str(project),
            "--request",
            str(project / REQUEST_RELATIVE),
            "--project-revision",
            project_revision,
            "--infrastructure-revision",
            INFRASTRUCTURE_REVISION,
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


@unittest.skipUnless((PROJECT / REQUEST_RELATIVE).is_file(), "Project Repository fixtures are unavailable")
class SyntheticReleaseTests(unittest.TestCase):
    def test_two_runs_are_byte_identical_and_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            one = run_release(PROJECT, first)
            two = run_release(PROJECT, second)
            self.assertEqual(one.returncode, 0, one.stderr)
            self.assertEqual(two.returncode, 0, two.stderr)
            self.assertEqual(
                {path.name: path.read_bytes() for path in first.iterdir()},
                {path.name: path.read_bytes() for path in second.iterdir()},
            )
            decision = json.loads((first / "release-decision.json").read_bytes())
            release = json.loads((first / "model-release.json").read_bytes())
            evidence = json.loads((first / "evidence-package.json").read_bytes())
            self.assertEqual(decision["outcome"], "rejected")
            self.assertEqual(release["selection"], "base")
            self.assertIsNone(release["adapter"])
            self.assertTrue(decision["synthetic"])
            self.assertEqual(evidence["projectRevision"], PROJECT_REVISION)
            self.assertEqual(evidence["infrastructureRevision"], INFRASTRUCTURE_REVISION)
            self.assertEqual(len(evidence["entries"]), 13)

    def test_manifest_and_evidence_output_digests_are_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            result = run_release(PROJECT, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {}
            for line in (output / "manifest.sha256").read_text(encoding="ascii").splitlines():
                digest, name = line.split("  ", 1)
                expected[name] = digest
            for name, digest in expected.items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            evidence = json.loads((output / "evidence-package.json").read_bytes())
            entries = {entry["path"]: entry["digest"] for entry in evidence["entries"]}
            self.assertEqual(entries["output/release-decision.json"], evidence["releaseDecisionDigest"])
            self.assertEqual(entries["output/model-release.json"], evidence["modelReleaseDigest"])

    def test_revision_mismatch_fails_before_writing_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            result = run_release(PROJECT, output, project_revision="3" * 40)
            self.assertEqual(result.returncode, 2)
            self.assertIn("project revision does not match", result.stderr)
            self.assertFalse(output.exists())

    def test_tampered_configuration_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied_project = Path(temporary) / "project"
            shutil.copytree(PROJECT / "contracts", copied_project / "contracts")
            shutil.copytree(PROJECT / "fixtures", copied_project / "fixtures")
            configuration = copied_project / REQUEST_RELATIVE.parent / "release-configuration.json"
            value = json.loads(configuration.read_bytes())
            value["environment"] = "tampered"
            configuration.write_text(
                json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            output = Path(temporary) / "out"
            result = run_release(copied_project, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("configuration immutable digest", result.stderr)
            self.assertFalse(output.exists())

    def test_tampered_payload_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied_project = Path(temporary) / "project"
            shutil.copytree(PROJECT / "contracts", copied_project / "contracts")
            shutil.copytree(PROJECT / "fixtures", copied_project / "fixtures")
            payload = copied_project / "fixtures/releases/rejected/adapter-payload.txt"
            payload.write_text("tampered", encoding="utf-8")
            output = Path(temporary) / "out"
            result = run_release(copied_project, output)
            self.assertEqual(result.returncode, 2)
            self.assertIn("payload size", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

