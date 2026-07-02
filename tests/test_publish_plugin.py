import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "publish-plugin.py"


def load_module():
    spec = importlib.util.spec_from_file_location("publish_plugin", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PublishPluginTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.plugin = self.repo_root / "plugins" / "sample"
        (self.plugin / ".claude-plugin").mkdir(parents=True)
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "sample", "version": "1.2.3"}),
            encoding="utf-8",
        )
        (self.repo_root / ".claude-plugin").mkdir()
        (self.repo_root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"plugins": [{"name": "sample", "version": "1.2.3"}]}),
            encoding="utf-8",
        )
        (self.repo_root / "README.md").write_text("sample 1.2.3\n", encoding="utf-8")
        (self.repo_root / "CLAUDE.md").write_text("sample 1.2.3\n", encoding="utf-8")
        (self.plugin / "README.md").write_text(
            "**Version:** 1.2.3\n\n## Changelog\n\n### 1.2.3\n- Initial release\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_publish(self):
        module = load_module()
        module.REPO_ROOT = str(self.repo_root)
        with patch("sys.argv", ["publish-plugin.py", "sample", "patch"]):
            with redirect_stdout(StringIO()):
                module.main()

    def test_publish_updates_root_claude_marketplace(self):
        self.run_publish()

        marketplace = json.loads(
            (self.repo_root / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(marketplace["plugins"][0]["version"], "1.2.4")

    def test_publish_updates_codex_manifest_for_dual_target_plugin(self):
        (self.plugin / ".codex-plugin").mkdir()
        (self.plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "sample", "version": "1.2.3"}),
            encoding="utf-8",
        )

        self.run_publish()

        manifest = json.loads(
            (self.plugin / ".codex-plugin" / "plugin.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["version"], "1.2.4")

    def test_publish_syncs_bundled_mcp_package_versions(self):
        mcp = self.plugin / "mcp"
        mcp.mkdir()
        (mcp / "package.json").write_text(
            json.dumps({"name": "sample-mcp", "version": "1.2.2"}),
            encoding="utf-8",
        )
        (mcp / "package-lock.json").write_text(
            json.dumps(
                {
                    "name": "sample-mcp",
                    "version": "1.2.2",
                    "packages": {"": {"name": "sample-mcp", "version": "1.2.2"}},
                }
            ),
            encoding="utf-8",
        )

        self.run_publish()

        pkg = json.loads((mcp / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["version"], "1.2.4")
        lock = json.loads((mcp / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["version"], "1.2.4")
        self.assertEqual(lock["packages"][""]["version"], "1.2.4")

    def test_publish_preserves_historical_plugin_changelog_versions(self):
        self.run_publish()

        readme = (self.plugin / "README.md").read_text(encoding="utf-8")
        self.assertIn("**Version:** 1.2.4", readme)
        self.assertIn("### 1.2.3", readme)


if __name__ == "__main__":
    unittest.main()
