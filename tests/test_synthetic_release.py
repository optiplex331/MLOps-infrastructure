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
PROJECT_SOURCE = Path(os.environ.get("MLOPS_PROJECT_REPO", ROOT.parent / "MLOps"))
REQUEST_RELATIVE = Path("fixtures/releases/rejected/release-request.template.json")


def git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def initialize(repo: Path) -> str:
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Synthetic Test")
    git(repo, "config", "user.email", "synthetic@example.invalid")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "test: initialize fixture repository")
    return git(repo, "rev-parse", "HEAD")


class Repositories:
    def __init__(self, root: Path) -> None:
        self.infrastructure = root / "MLOps-infrastructure"
        self.project = root / "MLOps"
        shutil.copytree(
            ROOT,
            self.infrastructure,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
        )
        self.project.mkdir()
        shutil.copytree(PROJECT_SOURCE / "contracts", self.project / "contracts")
        shutil.copytree(PROJECT_SOURCE / "fixtures", self.project / "fixtures")
        self.infrastructure_revision = initialize(self.infrastructure)
        self.project_revision = initialize(self.project)

    def commit_project_change(self, message: str) -> None:
        git(self.project, "add", ".")
        git(self.project, "commit", "-m", message)
        self.project_revision = git(self.project, "rev-parse", "HEAD")

    def run(
        self,
        output: Path,
        *,
        project_revision: str | None = None,
        infrastructure_revision: str | None = None,
        project: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        project = project or self.project
        return subprocess.run(
            [
                str(self.infrastructure / "bin" / "run-synthetic-release"),
                "--project-repo",
                str(project),
                "--request",
                str(project / REQUEST_RELATIVE),
                "--project-revision",
                project_revision or self.project_revision,
                "--infrastructure-revision",
                infrastructure_revision or self.infrastructure_revision,
                "--output-dir",
                str(output),
            ],
            cwd=self.infrastructure,
            capture_output=True,
            text=True,
        )


@unittest.skipUnless((PROJECT_SOURCE / REQUEST_RELATIVE).is_file(), "Project templates are unavailable")
class SyntheticReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repositories = Repositories(self.root)

    def test_real_heads_are_materialized_and_two_runs_are_byte_identical(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        one = self.repositories.run(first)
        two = self.repositories.run(second)
        self.assertEqual(one.returncode, 0, one.stderr)
        self.assertEqual(two.returncode, 0, two.stderr)
        self.assertEqual(
            {path.name: path.read_bytes() for path in first.iterdir()},
            {path.name: path.read_bytes() for path in second.iterdir()},
        )
        request = json.loads((first / "release-request.json").read_bytes())
        artifact = json.loads((first / "model-artifact.json").read_bytes())
        decision = json.loads((first / "release-decision.json").read_bytes())
        release = json.loads((first / "model-release.json").read_bytes())
        evidence = json.loads((first / "evidence-package.json").read_bytes())
        self.assertEqual(request["projectRevision"], self.repositories.project_revision)
        self.assertEqual(request["infrastructureRevision"], self.repositories.infrastructure_revision)
        self.assertEqual(artifact["provenance"]["projectRevision"], self.repositories.project_revision)
        self.assertNotIn("${", (first / "release-request.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["outcome"], "rejected")
        self.assertEqual(release["selection"], "base")
        self.assertIsNone(release["adapter"])
        self.assertEqual(evidence["projectRevision"], self.repositories.project_revision)
        self.assertEqual(evidence["infrastructureRevision"], self.repositories.infrastructure_revision)

    def test_manifest_and_evidence_form_digest_closure(self) -> None:
        output = self.root / "out"
        result = self.repositories.run(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = {}
        for line in (output / "manifest.sha256").read_text(encoding="ascii").splitlines():
            digest, name = line.split("  ", 1)
            manifest[name] = "sha256:" + digest
        self.assertEqual(
            set(manifest),
            {
                "release-request.json",
                "model-artifact.json",
                "release-decision.json",
                "model-release.json",
                "evidence-package.json",
            },
        )
        for name, digest in manifest.items():
            self.assertEqual("sha256:" + hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
        evidence = json.loads((output / "evidence-package.json").read_bytes())
        entry_digests = {entry["digest"] for entry in evidence["entries"]}
        entry_paths = {entry["path"] for entry in evidence["entries"]}
        self.assertIn("project/fixtures/releases/rejected/release-request.template.json", entry_paths)
        self.assertIn("project/fixtures/releases/rejected/model-artifact.template.json", entry_paths)
        self.assertIn("output/release-request.json", entry_paths)
        self.assertIn("output/model-artifact.json", entry_paths)
        entries = {entry["path"]: entry["digest"] for entry in evidence["entries"]}
        self.assertEqual(entries["output/release-request.json"], manifest["release-request.json"])
        self.assertEqual(entries["output/model-artifact.json"], manifest["model-artifact.json"])
        artifact = json.loads((output / "model-artifact.json").read_bytes())
        referenced = {
            artifact["baseModel"]["digest"],
            artifact["tokenizer"]["digest"],
            artifact["payload"]["digest"],
            artifact["provenance"]["sourceDigest"],
        }
        self.assertTrue(referenced <= entry_digests)

    def test_non_head_revision_fails_before_outputs(self) -> None:
        output = self.root / "out"
        result = self.repositories.run(output, project_revision="0" * 40)
        self.assertEqual(result.returncode, 2)
        self.assertIn("cat-file", result.stderr)
        self.assertFalse(output.exists())

    def test_existing_non_head_commit_fails_before_outputs(self) -> None:
        previous = self.repositories.project_revision
        (self.repositories.project / "committed.txt").write_text("next revision\n", encoding="utf-8")
        self.repositories.commit_project_change("test: advance project head")
        output = self.root / "out"
        result = self.repositories.run(output, project_revision=previous)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must equal current HEAD", result.stderr)
        self.assertFalse(output.exists())

    def test_swapped_revisions_fail_before_outputs(self) -> None:
        output = self.root / "out"
        result = self.repositories.run(
            output,
            project_revision=self.repositories.infrastructure_revision,
            infrastructure_revision=self.repositories.project_revision,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_dirty_project_fails_before_outputs(self) -> None:
        output = self.root / "out"
        (self.repositories.project / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        result = self.repositories.run(output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("worktree must be clean", result.stderr)
        self.assertFalse(output.exists())

    def test_dirty_infrastructure_fails_before_outputs(self) -> None:
        output = self.root / "out"
        (self.repositories.infrastructure / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        result = self.repositories.run(output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Infrastructure Repository worktree must be clean", result.stderr)
        self.assertFalse(output.exists())

    def test_output_directory_inside_repository_is_rejected(self) -> None:
        output = self.repositories.infrastructure / "generated-output"
        result = self.repositories.run(output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("output directory must be outside", result.stderr)
        self.assertFalse(output.exists())

    def test_project_without_git_metadata_is_rejected(self) -> None:
        output = self.root / "out"
        copied = self.root / "project-without-git"
        shutil.copytree(self.repositories.project, copied, ignore=shutil.ignore_patterns(".git"))
        result = self.repositories.run(output, project=copied)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not an independent Git worktree", result.stderr)
        self.assertFalse(output.exists())

    def test_committed_tampered_configuration_fails_digest_check(self) -> None:
        configuration = self.repositories.project / REQUEST_RELATIVE.parent / "release-configuration.json"
        value = json.loads(configuration.read_bytes())
        value["environment"] = "tampered"
        configuration.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        self.repositories.commit_project_change("test: tamper configuration")
        output = self.root / "out"
        result = self.repositories.run(output)
        self.assertEqual(result.returncode, 2)
        self.assertIn("configuration immutable digest", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
