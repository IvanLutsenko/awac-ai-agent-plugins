import importlib.util
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
    make_cc_plugin,
    read_json,
    read_text,
    write_json,
)


def load_module():
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "adaptation", PLUGIN_ROOT / "scripts" / "adaptation.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adaptation = load_module()


class AdaptationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_analyze_writes_plan_and_state_without_touching_targets(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        target = plugin / "skills/generated-from-hooks/sessionstart/SKILL.md"

        report = adaptation.analyze(self.repo, plugin)

        self.assertEqual(report.exit_code, 0)
        self.assertEqual(report.status, "planned")
        self.assertTrue((plugin / ".plugin-cross-port/adaptation-plan.md").exists())
        self.assertTrue((plugin / ".plugin-cross-port/adaptation-state.json").exists())
        self.assertFalse(target.exists())

    def test_rendered_plan_contains_parseable_machine_block_for_hook(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")

        adaptation.analyze(self.repo, plugin)
        plan_text = read_text(plugin / ".plugin-cross-port/adaptation-plan.md")
        payload = adaptation.parse_plan(plan_text)
        first = payload["adaptations"][0]

        self.assertIn(adaptation.MACHINE_BLOCK_START, plan_text)
        self.assertEqual(payload["plan_hash"], adaptation.plan_payload_hash(payload))
        self.assertEqual(first["id"], "hooks-sessionstart")
        self.assertEqual(first["strategy"], "semantic")
        self.assertEqual(first["criticality"], "critical")

    def test_claude_plugin_root_command_creates_non_critical_semantic_adaptation(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_command(
            self.repo,
            "one",
            "main",
            "Read configuration from ${CLAUDE_PLUGIN_ROOT}/references/config.md",
        )

        report = adaptation.analyze(self.repo, plugin)

        command_adaptation = report.adaptations[0]
        self.assertEqual(command_adaptation["id"], "command-main-plugin-root-path")
        self.assertEqual(command_adaptation["strategy"], "semantic")
        self.assertEqual(command_adaptation["criticality"], "non-critical")

    def test_builtin_detectors_create_semantic_adaptations_only(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        add_cc_command(
            self.repo,
            "one",
            "main",
            "Read ${CLAUDE_PLUGIN_ROOT}/references/config.md",
        )

        report = adaptation.analyze(self.repo, plugin)

        self.assertEqual(
            {item["strategy"] for item in report.adaptations},
            {"semantic"},
        )

    def test_replay_reproducible_append_text_is_idempotent(self):
        plugin = make_cc_plugin(self.repo, "one")
        target = plugin / "skills/generated-from-hooks/sessionstart/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("Existing skill\n", encoding="utf-8")
        payload = {
            "adaptations": [
                {
                    "id": "append-review",
                    "strategy": "reproducible",
                    "target_files": [
                        "skills/generated-from-hooks/sessionstart/SKILL.md"
                    ],
                    "action": {
                        "type": "append_text",
                        "text": "\nReview note\n",
                    },
                }
            ]
        }

        first = adaptation.replay_reproducible_adaptations(plugin, payload)
        second = adaptation.replay_reproducible_adaptations(plugin, payload)

        self.assertEqual(first, [target])
        self.assertEqual(second, [])
        self.assertEqual(read_text(target).count("Review note"), 1)

    def test_replay_rejects_target_path_outside_plugin(self):
        plugin = make_cc_plugin(self.repo, "one")
        outside = self.repo / "outside.md"
        payload = {
            "adaptations": [
                {
                    "id": "escape",
                    "strategy": "reproducible",
                    "target_files": ["../../outside.md"],
                    "action": {"type": "append_text", "text": "escape"},
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "outside plugin"):
            adaptation.replay_reproducible_adaptations(plugin, payload)

        self.assertFalse(outside.exists())

    def test_apply_rejects_stale_source_snapshot(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        adaptation.analyze(self.repo, plugin)
        manifest_path = plugin / ".claude-plugin" / "plugin.json"
        manifest = read_json(manifest_path)
        manifest["description"] = "Changed after planning."
        write_json(manifest_path, manifest)

        report = adaptation.apply_plan(self.repo, plugin)

        self.assertEqual(report.exit_code, 1)
        self.assertIn("stale source snapshot", report.error)

    def test_apply_writes_all_targets_and_marks_state_applied(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        target = plugin / "skills/generated-from-hooks/sessionstart/SKILL.md"
        state_path = plugin / ".plugin-cross-port/adaptation-state.json"
        adaptation.analyze(self.repo, plugin)

        report = adaptation.apply_plan(self.repo, plugin)

        self.assertEqual(report.exit_code, 0)
        self.assertTrue(target.exists())
        self.assertEqual(read_json(state_path)["status"], "applied")

    def test_apply_rejects_tampered_plan_hash(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        adaptation.analyze(self.repo, plugin)
        plan_path = plugin / ".plugin-cross-port/adaptation-plan.md"
        payload = adaptation.parse_plan(read_text(plan_path))
        payload["adaptations"][0]["rationale"] = "Changed without refreshing hash."
        plan_path.write_text(adaptation.render_plan(payload), encoding="utf-8")

        report = adaptation.apply_plan(self.repo, plugin)

        self.assertEqual(report.exit_code, 1)
        self.assertIn("stale plan hash", report.error)

    def test_apply_rejects_target_path_outside_plugin(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        outside = self.repo / "outside.md"
        adaptation.analyze(self.repo, plugin)
        plan_path = plugin / ".plugin-cross-port/adaptation-plan.md"
        payload = adaptation.parse_plan(read_text(plan_path))
        payload["adaptations"][0]["target_files"] = ["../../outside.md"]
        payload["plan_hash"] = adaptation.plan_payload_hash(payload)
        plan_path.write_text(adaptation.render_plan(payload), encoding="utf-8")

        report = adaptation.apply_plan(self.repo, plugin)

        self.assertEqual(report.exit_code, 1)
        self.assertIn("outside plugin", report.error)
        self.assertFalse(outside.exists())

    def test_apply_rolls_back_all_targets_when_one_action_fails(self):
        plugin = make_cc_plugin(self.repo, "one")
        add_cc_hook(self.repo, "one")
        first_target = plugin / "skills/generated-from-hooks/sessionstart/SKILL.md"
        unknown_target = plugin / "skills/generated-from-hooks/unknown/SKILL.md"
        adaptation.analyze(self.repo, plugin)
        plan_path = plugin / ".plugin-cross-port/adaptation-plan.md"
        payload = adaptation.parse_plan(read_text(plan_path))
        payload["adaptations"].append(
            {
                "id": "unknown-action",
                "strategy": "semantic",
                "criticality": "critical",
                "rationale": "Exercise apply rollback.",
                "source_files": [".claude-plugin/plugin.json"],
                "target_files": ["skills/generated-from-hooks/unknown/SKILL.md"],
                "source_snapshot": payload["source_snapshot"],
                "action": {
                    "type": "unknown_action",
                },
            }
        )
        payload["plan_hash"] = adaptation.plan_payload_hash(payload)
        plan_path.write_text(adaptation.render_plan(payload), encoding="utf-8")

        report = adaptation.apply_plan(self.repo, plugin)

        self.assertEqual(report.exit_code, 1)
        self.assertFalse(first_target.exists())
        self.assertFalse(unknown_target.exists())

    def test_analyze_rejects_codex_source(self):
        plugin = make_cc_plugin(self.repo, "one")
        write_json(
            plugin / ".plugin-cross-port.json",
            {
                "version": 2,
                "plugin": "one",
                "source_of_truth": "codex",
                "status": "synced",
                "manually_maintained": [],
            },
        )

        with self.assertRaisesRegex(ValueError, "claude-code"):
            adaptation.analyze(self.repo, plugin)

    def test_parse_plan_requires_machine_block(self):
        with self.assertRaisesRegex(ValueError, "machine-readable"):
            adaptation.parse_plan("# Adaptation Plan\n")


if __name__ == "__main__":
    unittest.main()
