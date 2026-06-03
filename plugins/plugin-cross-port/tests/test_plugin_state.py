import importlib.util
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "plugin_state", PLUGIN_ROOT / "scripts" / "plugin_state.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PluginStateTest(unittest.TestCase):
    def test_round_trip_nested_marketplace_state(self):
        state = load_module()
        payload = {
            "version": 1,
            "source_of_truth": "claude-code",
            "source_marketplace": ".claude-plugin/marketplace.json",
            "targets": {"codex": ".agents/plugins/marketplace.json"},
            "plugins": {
                "sample": {
                    "status": "failed",
                    "target": "codex",
                    "last_error": "manifest validation failed",
                }
            },
        }
        self.assertEqual(state.loads(state.dumps(payload)), payload)

    def test_plugin_state_defaults_to_version_two(self):
        state = load_module()
        payload = state.new_plugin_state("sample", "codex")
        self.assertEqual(
            payload,
            {
                "version": 2,
                "plugin": "sample",
                "source_of_truth": "codex",
                "status": "synced",
                "manually_maintained": [],
            },
        )

    def test_load_missing_returns_default(self):
        state = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.yaml"
            self.assertEqual(state.load(path, default={"version": 1}), {"version": 1})

    def test_loads_legacy_plugin_state(self):
        state = load_module()
        payload = state.loads(
            "source_of_truth: claude-code\n"
            "manually_maintained:\n"
            "  - skills/generated-from-commands/main/SKILL.md\n"
        )
        self.assertEqual(payload["source_of_truth"], "claude-code")
        self.assertEqual(
            payload["manually_maintained"],
            ["skills/generated-from-commands/main/SKILL.md"],
        )


if __name__ == "__main__":
    unittest.main()
