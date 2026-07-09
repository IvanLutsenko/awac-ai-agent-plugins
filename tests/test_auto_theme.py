import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "plugins" / "auto-theme" / "sync-theme.sh"


class AutoThemeScriptTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.bin_dir = self.root / "bin"
        self.plugin_root = self.root / "plugin"
        self.home.mkdir()
        self.bin_dir.mkdir()
        shutil.copytree(REPO_ROOT / "plugins" / "auto-theme", self.plugin_root)
        self._write_defaults_script()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_defaults_script(self):
        script = self.bin_dir / "defaults"
        script.write_text(
            "#!/bin/sh\n"
            "if [ \"$AUTO_THEME_MODE\" = \"dark\" ]; then\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        script.chmod(0o755)

    def _run(self, *, mode="light"):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["CLAUDE_PLUGIN_ROOT"] = str(self.plugin_root)
        env["AUTO_THEME_MODE"] = mode
        return subprocess.run(
            ["bash", str(self.plugin_root / "sync-theme.sh")],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def _write_claude_files(self, settings_payload, claude_payload=None):
        claude_dir = self.home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "settings.json").write_text(
            json.dumps(settings_payload), encoding="utf-8"
        )
        if claude_payload is not None:
            (self.home / ".claude.json").write_text(
                json.dumps(claude_payload), encoding="utf-8"
            )

    def _write_codex_config(self):
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        (codex_dir / "config.toml").write_text("[tui]\n", encoding="utf-8")

    def test_warns_and_skips_malformed_claude_json(self):
        self._write_claude_files({"theme": "custom:gruvbox-light"})
        (self.home / ".claude.json").write_text("{bad json", encoding="utf-8")
        self._write_codex_config()

        result = self._run()

        self.assertEqual(result.returncode, 0)
        self.assertIn("WARN:", result.stderr)
        self.assertIn(".claude.json malformed, skipped", result.stderr)

    def test_warns_and_preserves_unknown_custom_theme(self):
        self._write_claude_files({"theme": "custom:dracula"})
        self._write_codex_config()

        result = self._run(mode="dark")

        settings = json.loads(
            (self.home / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(settings["theme"], "custom:dracula")
        self.assertIn("WARN:", result.stderr)
        self.assertIn("custom:dracula has no dark pair, skipped", result.stderr)

    def test_warns_when_target_file_is_not_writable(self):
        self._write_claude_files({"theme": "custom:gruvbox-light"})
        self._write_codex_config()
        settings_path = self.home / ".claude" / "settings.json"
        settings_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        result = self._run(mode="dark")

        self.assertEqual(result.returncode, 0)
        self.assertIn("WARN:", result.stderr)
        self.assertIn("settings.json not writable", result.stderr)


if __name__ == "__main__":
    unittest.main()
