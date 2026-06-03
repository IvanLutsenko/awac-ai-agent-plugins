import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

from helpers import make_cc_marketplace, make_cc_plugin, read_json, write_json


class PreCommitHookTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)
        self.git_run("git", "init")
        self.git_run("git", "config", "user.email", "test@example.com")
        self.git_run("git", "config", "user.name", "Tester")
        self.install_cross_port()
        self.install_hook()

    def tearDown(self):
        self.temp_dir.cleanup()

    def git_run(self, *args: str, check: bool = True):
        return subprocess.run(
            args,
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=check,
        )

    def install_cross_port(self):
        scripts = self.repo / "plugins/plugin-cross-port/scripts"
        shutil.copytree(PLUGIN_ROOT / "scripts", scripts)

    def install_hook(self):
        hooks = self.repo / ".githooks"
        hooks.mkdir()
        shutil.copy(REPO_ROOT / ".githooks/pre-commit", hooks / "pre-commit")
        (hooks / "pre-commit").chmod(0o755)
        self.git_run("git", "config", "core.hooksPath", ".githooks")

    def attach_baseline(self, names=("one",)):
        make_cc_marketplace(self.repo, list(names))
        for name in names:
            make_cc_plugin(self.repo, name)
        result = self.git_run(
            sys.executable,
            "plugins/plugin-cross-port/scripts/cross_port.py",
            "--repo-root",
            ".",
            "marketplace",
            "attach",
            "--source",
            "claude-code",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.git_run("git", "add", "-A")
        self.git_run("git", "commit", "--no-verify", "-m", "baseline")

    def staged_names(self, *extra: str) -> list[str]:
        result = self.git_run("git", "diff", "--cached", "--name-only", *extra)
        return result.stdout.splitlines()

    def test_authoritative_side_edit_runs_changed_only_sync(self):
        self.attach_baseline()
        command = self.repo / "plugins/one/commands/main.md"
        command.parent.mkdir(exist_ok=True)
        command.write_text("---\ndescription: Main\n---\n\nBody\n", encoding="utf-8")
        self.git_run("git", "add", "plugins/one/commands/main.md")

        result = self.git_run(".githooks/pre-commit", check=False)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(
            "plugins/one/skills/generated-from-commands/main/SKILL.md",
            self.staged_names(),
        )

    def test_generated_side_edit_is_rejected(self):
        self.attach_baseline()
        generated = self.repo / "plugins/one/.codex-plugin/plugin.json"
        payload = read_json(generated)
        payload["version"] = "manual"
        write_json(generated, payload)
        self.git_run("git", "add", "plugins/one/.codex-plugin/plugin.json")

        result = self.git_run(".githooks/pre-commit", check=False)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Source of truth: claude-code", result.stdout + result.stderr)

    def test_staged_deletion_is_staged_after_sync(self):
        self.attach_baseline(("one", "two"))
        marketplace = self.repo / ".claude-plugin/marketplace.json"
        payload = read_json(marketplace)
        payload["plugins"] = [entry for entry in payload["plugins"] if entry["name"] != "one"]
        write_json(marketplace, payload)
        self.git_run("git", "add", ".claude-plugin/marketplace.json")

        result = self.git_run(".githooks/pre-commit", check=False)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        deleted = self.staged_names("--diff-filter=D")
        self.assertTrue(any(name.startswith("plugins/one/") for name in deleted), deleted)


if __name__ == "__main__":
    unittest.main()
