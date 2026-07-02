import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

from helpers import (
    add_cc_command,
    add_cc_hook,
    make_cc_marketplace,
    make_cc_plugin,
    read_json,
    write_json,
)


def load_module(name: str):
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN_ROOT / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adaptation = load_module("adaptation")
reconcile = load_module("reconcile")


class ReconcileAdaptationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def reconciler(self):
        return reconcile.Reconciler(self.repo)

    def plugin(self) -> Path:
        return self.repo / "plugins" / "one"

    def attach_cc_marketplace(self) -> None:
        make_cc_marketplace(self.repo, ["one"])
        make_cc_plugin(self.repo, "one")
        self.reconciler().attach_marketplace("claude-code")

    def test_stale_critical_semantic_adaptation_marks_codex_not_available(self):
        self.attach_cc_marketplace()
        add_cc_hook(self.repo, "one")
        adaptation.analyze(self.repo, self.plugin())
        adaptation.apply_plan(self.repo, self.plugin())
        manifest_path = self.plugin() / ".claude-plugin/plugin.json"
        manifest = read_json(manifest_path)
        manifest["description"] = "Changed after adaptation."
        write_json(manifest_path, manifest)

        report = self.reconciler().sync()

        entry = read_json(self.repo / ".agents/plugins/marketplace.json")["plugins"][0]
        plugin_state = read_json(self.plugin() / ".plugin-cross-port.json")
        self.assertEqual(report.exit_code, 1)
        self.assertEqual(report.results[0].status, "needs-review")
        self.assertEqual(entry["policy"]["installation"], "NOT_AVAILABLE")
        self.assertEqual(plugin_state["status"], "needs-review")

    def test_stale_non_critical_semantic_adaptation_keeps_codex_available(self):
        self.attach_cc_marketplace()
        command = add_cc_command(
            self.repo,
            "one",
            "main",
            "Read configuration from ${CLAUDE_PLUGIN_ROOT}/references/config.md",
        )
        adaptation.analyze(self.repo, self.plugin())
        adaptation.apply_plan(self.repo, self.plugin())
        command.write_text(
            "---\ndescription: Main command\n---\n\n"
            "Read changed configuration from ${CLAUDE_PLUGIN_ROOT}/references/config.md\n",
            encoding="utf-8",
        )

        report = self.reconciler().sync()

        entry = read_json(self.repo / ".agents/plugins/marketplace.json")["plugins"][0]
        marketplace_state = read_json(self.repo / ".plugin-cross-port.marketplace.json")
        plugin_state = read_json(self.plugin() / ".plugin-cross-port.json")
        self.assertEqual(report.exit_code, 0)
        self.assertEqual(report.results[0].status, "synced")
        self.assertIn("stale non-critical adaptation", report.results[0].error)
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertNotIn("last_error", marketplace_state["plugins"]["one"])
        self.assertNotIn("last_error", plugin_state)
        self.assertIn("stale non-critical adaptation", plugin_state["warnings"][0])

    def test_reproducible_adaptation_replays_after_sync(self):
        self.attach_cc_marketplace()
        add_cc_command(self.repo, "one", "main", "Body")
        self.reconciler().sync()
        target = self.plugin() / "skills/generated-from-commands/main/SKILL.md"
        state_path = self.plugin() / ".plugin-cross-port/adaptation-state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "plugin": "one",
                    "source_of_truth": "claude-code",
                    "status": "applied",
                    "adaptations": [
                        {
                            "id": "append-note",
                            "strategy": "reproducible",
                            "target_files": [
                                "skills/generated-from-commands/main/SKILL.md"
                            ],
                            "action": {
                                "type": "append_text",
                                "text": "\nAppended note\n",
                            },
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        target.write_text("Generated again\n", encoding="utf-8")

        report = self.reconciler().sync()

        self.assertEqual(report.exit_code, 0)
        self.assertIn("Appended note", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
