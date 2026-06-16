import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

from helpers import make_cc_plugin, make_codex_marketplace, make_codex_plugin, read_json


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PLUGIN_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


cc_to_codex = load_module("convert_cc_to_codex", "scripts/convert_cc_to_codex.py")
codex_to_cc = load_module("convert_codex_to_cc", "scripts/convert_codex_to_cc.py")


class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.codex_marketplace = make_codex_marketplace(self.repo_root, [])

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_cc_plugin(self, name="sample"):
        return make_cc_plugin(self.repo_root, name)

    def make_codex_plugin(self, name="sample"):
        return make_codex_plugin(self.repo_root, name)

    def test_cc_to_codex_removes_stale_generated_skill(self):
        plugin = self.make_cc_plugin()
        stale = plugin / "skills" / "generated-from-commands" / "removed" / "SKILL.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale", encoding="utf-8")

        converter = cc_to_codex.Converter(plugin, self.repo_root, False, False, False)

        self.assertEqual(converter.run(), 0)
        self.assertFalse(stale.exists())

    def test_cc_to_codex_rewrites_plugin_root_to_repo_relative_path(self):
        plugin = self.make_cc_plugin("drawbridge")
        command = plugin / "commands" / "draw.md"
        command.parent.mkdir()
        command.write_text(
            "---\n"
            "description: Draw\n"
            "allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/*)\n"
            "---\n\n"
            "source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh\n",
            encoding="utf-8",
        )

        self.assertEqual(
            cc_to_codex.Converter(plugin, self.repo_root, False, False, False).run(), 0
        )

        skill = (plugin / "skills/generated-from-commands/draw/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("source plugins/drawbridge/scripts/lib.sh", skill)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill)
        self.assertNotIn("remove `allowed-tools`", skill)

    def test_cc_to_codex_preserves_plugin_relative_manually_maintained_skill(self):
        plugin = self.make_cc_plugin()
        command = plugin / "commands" / "kept.md"
        command.parent.mkdir()
        command.write_text("---\ndescription: Kept\n---\nnew body\n", encoding="utf-8")
        generated = plugin / "skills" / "generated-from-commands" / "kept" / "SKILL.md"
        generated.parent.mkdir(parents=True)
        generated.write_text("manual body", encoding="utf-8")
        (plugin / ".plugin-cross-port.yaml").write_text(
            "manually_maintained:\n"
            "  - skills/generated-from-commands/kept/SKILL.md\n",
            encoding="utf-8",
        )

        converter = cc_to_codex.Converter(plugin, self.repo_root, False, True, False)

        self.assertEqual(converter.run(), 0)
        self.assertEqual(generated.read_text(encoding="utf-8"), "manual body")

    def test_codex_to_cc_removes_stale_generated_command(self):
        plugin = self.make_codex_plugin()
        stale = plugin / "commands" / "generated-from-codex-removed.md"
        stale.parent.mkdir()
        stale.write_text("stale", encoding="utf-8")

        converter = codex_to_cc.ReverseConverter(
            plugin, self.repo_root, False, False, False
        )

        self.assertEqual(converter.run(), 0)
        self.assertFalse(stale.exists())

    def test_cc_to_codex_can_skip_marketplace_side_effects(self):
        plugin = self.make_cc_plugin()
        converter = cc_to_codex.Converter(
            plugin, self.repo_root, False, False, False, sync_marketplace=False
        )
        self.assertEqual(converter.run(), 0)
        self.assertEqual(read_json(self.codex_marketplace)["plugins"], [])

    def test_codex_to_cc_accepts_orchestration_mode(self):
        plugin = self.make_codex_plugin()
        converter = codex_to_cc.ReverseConverter(
            plugin, self.repo_root, False, False, False, sync_marketplace=False
        )
        self.assertEqual(converter.run(), 0)

    def _write_agent(self, plugin: Path, name: str, body: str = "System prompt.") -> None:
        agent = plugin / "agents" / f"{name}.md"
        agent.parent.mkdir(exist_ok=True)
        # CC agents pack <example> trigger blocks into a quoted single-line
        # description with literal \n escapes.
        agent.write_text(
            f'---\n'
            f'name: {name}\n'
            f'description: "Reviews code. Use when reviewing.\\n\\nExamples:\\n'
            f'<example>\\nuser: \\"review\\"\\n</example>"\n'
            f'tools: Read\n'
            f'---\n\n'
            f'{body}\n',
            encoding="utf-8",
        )

    def test_cc_to_codex_converts_agent_to_skill(self):
        plugin = self.make_cc_plugin("combined-review")
        self._write_agent(plugin, "code-reviewer", "Run ${CLAUDE_PLUGIN_ROOT}/x.sh")

        self.assertEqual(
            cc_to_codex.Converter(plugin, self.repo_root, False, False, False).run(), 0
        )

        skill_path = plugin / "skills/generated-from-agents/code-reviewer/SKILL.md"
        self.assertTrue(skill_path.exists())
        skill = skill_path.read_text(encoding="utf-8")
        # Description cleaned: examples block dropped, escapes gone.
        self.assertIn("description: Reviews code. Use when reviewing.", skill)
        self.assertNotIn("Examples:", skill)
        self.assertNotIn("<example>", skill)
        self.assertNotIn("\\n", skill)
        self.assertIn("name: combined-review-code-reviewer", skill)
        # Body path rewritten, agent body preserved.
        self.assertIn("Run plugins/combined-review/x.sh", skill)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill)

        decision = read_json(plugin / ".plugin-cross-port.yaml")
        self.assertTrue(decision["decisions"]["agents_converted"])

    def test_cc_to_codex_decision_file_round_trips_across_reruns(self):
        # Regression: the decision file was written as nested YAML but read back
        # with a JSON-first loader that rejected nesting, crashing every re-run.
        plugin = self.make_cc_plugin("combined-review")
        self._write_agent(plugin, "code-reviewer")

        self.assertEqual(
            cc_to_codex.Converter(plugin, self.repo_root, False, False, False).run(), 0
        )
        # Written file must be valid JSON (round-trips with plugin_state.load).
        read_json(plugin / ".plugin-cross-port.yaml")
        # Second run loads the file it just wrote — no crash, idempotent.
        self.assertEqual(
            cc_to_codex.Converter(plugin, self.repo_root, False, False, False).run(), 0
        )


if __name__ == "__main__":
    unittest.main()
