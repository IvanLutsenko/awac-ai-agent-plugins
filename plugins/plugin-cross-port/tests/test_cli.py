import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
SCRIPT = TESTS_ROOT.parents[0] / "scripts" / "cross_port.py"
sys.path.insert(0, str(TESTS_ROOT))

from helpers import add_cc_hook, make_cc_marketplace, make_cc_plugin, read_json, write_json


class CliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(self.repo), *args],
            text=True,
            capture_output=True,
        )

    def attach_one(self):
        make_cc_marketplace(self.repo, ["one"])
        make_cc_plugin(self.repo, "one")
        return self.run_cli("marketplace", "attach", "--source", "claude-code")

    def attach_one_with_hook(self):
        self.attach_one()
        add_cc_hook(self.repo, "one")

    def test_marketplace_attach_requires_source(self):
        result = self.run_cli("marketplace", "attach")
        self.assertNotEqual(result.returncode, 0)

    def test_marketplace_attach_reports_synced_count(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        make_cc_plugin(self.repo, "two")

        result = self.run_cli("marketplace", "attach", "--source", "claude-code")

        self.assertEqual(result.returncode, 0)
        self.assertIn("Synced:       2", result.stdout)

    def test_marketplace_attach_only_limits_plugins(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        make_cc_plugin(self.repo, "two")

        result = self.run_cli(
            "marketplace", "attach", "--source", "claude-code", "--only", "one"
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Synced:       1", result.stdout)
        self.assertFalse((self.repo / "plugins/two/.codex-plugin/plugin.json").exists())

    def test_marketplace_attach_exclude_limits_plugins(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        make_cc_plugin(self.repo, "two")

        result = self.run_cli(
            "marketplace", "attach", "--source", "claude-code", "--exclude", "two"
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Synced:       1", result.stdout)
        self.assertFalse((self.repo / "plugins/two/.codex-plugin/plugin.json").exists())

    def test_marketplace_sync_returns_failure_for_invalid_authoritative_plugin(self):
        make_cc_marketplace(self.repo, ["one", "two"])
        make_cc_plugin(self.repo, "one")
        (self.repo / "plugins/two").mkdir(parents=True)
        self.run_cli("marketplace", "attach", "--source", "claude-code")

        result = self.run_cli("marketplace", "sync")

        self.assertEqual(result.returncode, 1)

    def test_marketplace_check_returns_failure_after_generated_mutation(self):
        self.attach_one()
        generated = self.repo / "plugins/one/.codex-plugin/plugin.json"
        payload = read_json(generated)
        payload["version"] = "stale"
        write_json(generated, payload)

        result = self.run_cli("marketplace", "check")

        self.assertEqual(result.returncode, 1)

    def test_plugin_convert_without_root_state_does_not_create_marketplace(self):
        plugin = make_cc_plugin(self.repo, "one")

        result = self.run_cli(
            "plugin", "convert", str(plugin), "--from", "claude-code", "--to", "codex"
        )

        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.repo / ".agents/plugins/marketplace.json").exists())

    def test_plugin_attach_requires_source(self):
        make_cc_plugin(self.repo, "one")
        result = self.run_cli("plugin", "attach", "plugins/one")
        self.assertNotEqual(result.returncode, 0)

    def test_plugin_adapt_writes_plan_without_target_changes(self):
        self.attach_one_with_hook()
        plan = self.repo / "plugins/one/.plugin-cross-port/adaptation-plan.md"
        target = self.repo / "plugins/one/skills/generated-from-hooks/sessionstart/SKILL.md"

        result = self.run_cli("plugin", "adapt", "plugins/one")

        self.assertEqual(result.returncode, 0)
        self.assertTrue(plan.exists())
        self.assertFalse(target.exists())

    def test_plugin_adapt_apply_writes_targets(self):
        self.attach_one_with_hook()
        target = self.repo / "plugins/one/skills/generated-from-hooks/sessionstart/SKILL.md"

        plan_result = self.run_cli("plugin", "adapt", "plugins/one")
        apply_result = self.run_cli("plugin", "adapt", "plugins/one", "--apply")

        self.assertEqual(plan_result.returncode, 0)
        self.assertEqual(apply_result.returncode, 0)
        self.assertTrue(target.exists())

    def test_plugin_adapt_apply_rejects_stale_plan(self):
        self.attach_one_with_hook()
        manifest_path = self.repo / "plugins/one/.claude-plugin/plugin.json"
        manifest = read_json(manifest_path)
        manifest["description"] = "Changed after planning."

        plan_result = self.run_cli("plugin", "adapt", "plugins/one")
        write_json(manifest_path, manifest)
        apply_result = self.run_cli("plugin", "adapt", "plugins/one", "--apply")

        self.assertEqual(plan_result.returncode, 0)
        self.assertEqual(apply_result.returncode, 1)
        self.assertIn(
            "stale source snapshot",
            apply_result.stdout + apply_result.stderr,
        )

    def test_plugin_switch_source_updates_state_after_clean_sync(self):
        self.attach_one()

        result = self.run_cli("plugin", "switch-source", "plugins/one", "--to", "codex")

        self.assertEqual(result.returncode, 0)
        state = json.loads((self.repo / "plugins/one/.plugin-cross-port.json").read_text())
        self.assertEqual(state["source_of_truth"], "codex")

    def test_plugin_switch_source_rejects_stale_output(self):
        self.attach_one()
        generated = self.repo / "plugins/one/.codex-plugin/plugin.json"
        payload = read_json(generated)
        payload["version"] = "stale"
        write_json(generated, payload)

        result = self.run_cli("plugin", "switch-source", "plugins/one", "--to", "codex")

        self.assertEqual(result.returncode, 1)
        state = json.loads((self.repo / "plugins/one/.plugin-cross-port.json").read_text())
        self.assertEqual(state["source_of_truth"], "claude-code")


if __name__ == "__main__":
    unittest.main()
