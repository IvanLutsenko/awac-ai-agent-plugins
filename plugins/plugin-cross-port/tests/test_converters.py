import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


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
        (self.repo_root / ".agents" / "plugins").mkdir(parents=True)
        (self.repo_root / ".agents" / "plugins" / "marketplace.json").write_text(
            json.dumps({"plugins": []}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_cc_plugin(self, name="sample"):
        plugin = self.repo_root / "plugins" / name
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({
                "name": name,
                "version": "1.0.0",
                "description": "Sample plugin.",
                "author": {"name": "Tester"},
            }),
            encoding="utf-8",
        )
        return plugin

    def make_codex_plugin(self, name="sample"):
        plugin = self.repo_root / "plugins" / name
        (plugin / ".codex-plugin").mkdir(parents=True)
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({
                "name": name,
                "version": "1.0.0",
                "description": "Sample plugin.",
                "author": {"name": "Tester"},
                "interface": {"capabilities": ["Read"]},
            }),
            encoding="utf-8",
        )
        return plugin

    def test_cc_to_codex_removes_stale_generated_skill(self):
        plugin = self.make_cc_plugin()
        stale = plugin / "skills" / "generated-from-commands" / "removed" / "SKILL.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale", encoding="utf-8")

        converter = cc_to_codex.Converter(plugin, self.repo_root, False, False, False)

        self.assertEqual(converter.run(), 0)
        self.assertFalse(stale.exists())

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


if __name__ == "__main__":
    unittest.main()
