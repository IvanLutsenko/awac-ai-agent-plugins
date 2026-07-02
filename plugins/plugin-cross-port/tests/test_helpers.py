import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

from helpers import (
    add_cc_command,
    add_cc_hook,
    read_json,
    read_text,
    write_adaptation_state,
    write_plugin_file,
    write_json,
)


class HelpersTest(unittest.TestCase):
    def test_write_plugin_file_creates_side_plugin_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            write_plugin_file(
                root,
                "codex",
                "demo",
                "skills/demo/SKILL.md",
                "text",
            )

            path = (
                root
                / ".agents"
                / "plugins"
                / "plugins"
                / "demo"
                / "skills"
                / "demo"
                / "SKILL.md"
            )
            self.assertEqual(path.read_text(encoding="utf-8"), "text")

    def test_write_adaptation_state_creates_side_plugin_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            write_adaptation_state(
                root,
                "claude-code",
                "demo",
                {"version": 1, "steps": ["commands"]},
            )

            path = (
                root
                / ".claude-plugin"
                / "plugins"
                / "demo"
                / ".plugin-cross-port"
                / "adaptation-state.json"
            )
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"version": 1, "steps": ["commands"]},
            )

    def test_add_cc_command_creates_command_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            command = add_cc_command(root, "demo", "start", body="Run startup")

            self.assertEqual(
                command,
                root / "plugins" / "demo" / "commands" / "start.md",
            )
            self.assertEqual(
                read_text(command),
                "---\ndescription: Start command\n---\n\nRun startup\n",
            )

    def test_add_cc_hook_updates_manifest_and_writes_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "plugins" / "demo" / ".claude-plugin" / "plugin.json"
            write_json(manifest, {"name": "demo", "version": "1.0.0"})

            hook = add_cc_hook(root, "demo", event="SessionStart")

            self.assertEqual(
                hook,
                root / "plugins" / "demo" / "hooks" / "sessionstart.sh",
            )
            self.assertEqual(read_text(hook), "#!/bin/bash\nprintf 'hook'\n")
            self.assertEqual(
                read_json(manifest)["hooks"],
                {
                    "SessionStart": [
                        {
                            "type": "command",
                            "command": "hooks/sessionstart.sh",
                            "timeout": 10,
                        }
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()
