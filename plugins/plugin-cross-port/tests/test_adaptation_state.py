import importlib.util
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "adaptation_state", PLUGIN_ROOT / "scripts" / "adaptation_state.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AdaptationStateTest(unittest.TestCase):
    def test_source_snapshot_changes_when_source_file_content_changes(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"
            source = plugin / "commands" / "main.md"
            source.parent.mkdir(parents=True)
            source.write_text("first", encoding="utf-8")

            first = state.source_snapshot(plugin, ["commands/main.md"])
            source.write_text("second", encoding="utf-8")
            second = state.source_snapshot(plugin, ["commands/main.md"])

        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith(state.HASH_PREFIX))
        self.assertTrue(second.startswith(state.HASH_PREFIX))

    def test_source_snapshot_rejects_paths_outside_plugin(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"

            with self.assertRaisesRegex(ValueError, "outside plugin"):
                state.source_snapshot(plugin, ["../../outside.md"])

    def test_state_round_trip_uses_json_compatible_yaml(self):
        state = load_module()
        payload = {
            "version": 1,
            "plan_hash": "sha256:abc",
            "source_snapshot": "sha256:def",
            "status": "planned",
            "adaptations": [
                {
                    "id": "hooks-sessionstart",
                    "strategy": "semantic",
                    "criticality": "critical",
                    "rationale": "Session startup has no Codex equivalent.",
                    "source_files": [".claude-plugin/plugin.json", "hooks/sessionstart.sh"],
                    "target_files": ["skills/generated-from-hooks/sessionstart/SKILL.md"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"

            state.save(plugin, payload)

            self.assertEqual(state.load(plugin), payload)
            self.assertEqual(state.load(state.state_path(plugin)), payload)

    def test_missing_state_load_returns_empty_dict(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"

            self.assertEqual(state.load(plugin), {})

    def test_plan_hash_changes_when_plan_text_changes(self):
        state = load_module()

        self.assertNotEqual(state.plan_hash("first"), state.plan_hash("second"))

    def test_classify_staleness_detects_changed_non_critical_sources(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"
            source = plugin / "commands" / "main.md"
            source.parent.mkdir(parents=True)
            source.write_text("first", encoding="utf-8")
            payload = {
                "adaptations": [
                    {
                        "id": "command-path",
                        "criticality": "non-critical",
                        "source_files": ["commands/main.md"],
                    }
                ],
                "source_snapshot": state.source_snapshot(plugin, ["commands/main.md"]),
            }
            source.write_text("second", encoding="utf-8")

            result = state.classify_staleness(payload, plugin)

        self.assertEqual(
            result,
            {
                "stale": True,
                "critical": False,
                "status": "stale-non-critical",
                "source_snapshot": result["source_snapshot"],
            },
        )
        self.assertTrue(result["source_snapshot"].startswith(state.HASH_PREFIX))

    def test_classify_staleness_defaults_missing_criticality_to_critical(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"
            source = plugin / "commands" / "main.md"
            source.parent.mkdir(parents=True)
            source.write_text("first", encoding="utf-8")
            payload = {
                "adaptations": [{"id": "command-path", "source_files": ["commands/main.md"]}],
                "source_snapshot": state.source_snapshot(plugin, ["commands/main.md"]),
            }
            source.write_text("second", encoding="utf-8")

            result = state.classify_staleness(payload, plugin)

        self.assertTrue(result["stale"])
        self.assertTrue(result["critical"])
        self.assertEqual(result["status"], "stale-critical")

    def test_classify_staleness_uses_adaptation_level_source_snapshots(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"
            source = plugin / "commands" / "main.md"
            source.parent.mkdir(parents=True)
            source.write_text("first", encoding="utf-8")
            payload = {
                "adaptations": [
                    {
                        "id": "command-path",
                        "criticality": "critical",
                        "source_files": ["commands/main.md"],
                        "source_snapshot": state.source_snapshot(
                            plugin, ["commands/main.md"]
                        ),
                    }
                ],
            }
            source.write_text("second", encoding="utf-8")

            result = state.classify_staleness(payload, plugin)

        self.assertTrue(result["stale"])
        self.assertTrue(result["critical"])
        self.assertEqual(result["status"], "stale-critical")

    def test_classify_staleness_reports_current_for_unchanged_sources(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugins" / "one"
            source = plugin / "commands" / "main.md"
            source.parent.mkdir(parents=True)
            source.write_text("first", encoding="utf-8")
            payload = {
                "adaptations": [{"id": "command-path", "source_files": ["commands/main.md"]}],
                "source_snapshot": state.source_snapshot(plugin, ["commands/main.md"]),
            }

            result = state.classify_staleness(payload, plugin)

        self.assertFalse(result["stale"])
        self.assertFalse(result["critical"])
        self.assertEqual(result["status"], "current")


if __name__ == "__main__":
    unittest.main()
