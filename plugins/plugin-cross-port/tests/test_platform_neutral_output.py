import ast
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
SCRIPTS = sorted((PLUGIN_ROOT / "scripts").glob("*.py"))
sys.path.insert(0, str(TESTS_ROOT))

from helpers import make_cc_plugin, make_codex_marketplace, make_codex_plugin


def calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


class PlatformNeutralOutputTest(unittest.TestCase):
    """Generated files are committed and compared byte for byte, so a run on Windows
    must write what a run on macOS or Linux writes: LF line ends, `/` in paths."""

    def test_no_script_writes_through_write_text(self):
        offenders = [
            f"{path.name}:{node.lineno}"
            for path in SCRIPTS
            for node in calls(path)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "write_text"
        ]
        self.assertEqual(
            offenders,
            [],
            "write_text writes CRLF on Windows, and its newline= needs Python 3.10; "
            "use write_bytes(text.encode('utf-8'))",
        )

    def test_no_relative_path_is_stringified_with_the_os_separator(self):
        offenders = [
            f"{path.name}:{node.lineno}"
            for path in SCRIPTS
            for node in calls(path)
            if isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and node.args
            and isinstance(node.args[0], ast.Call)
            and isinstance(node.args[0].func, ast.Attribute)
            and node.args[0].func.attr in ("relative_to", "relpath")
        ]
        self.assertEqual(offenders, [], "str(<path>.relative_to(...)) gives backslashes on Windows")


class LegacyConsoleTest(unittest.TestCase):
    def load_console(self):
        spec = importlib.util.spec_from_file_location(
            "cross_port_console", PLUGIN_ROOT / "scripts" / "console.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_report_survives_a_legacy_console_code_page(self):
        module = self.load_console()
        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1251")
        with patch.object(sys, "stdout", console), patch.object(sys, "stderr", console):
            module.utf8_console()
            print("  ✅ generated")
            sys.stdout.flush()

        self.assertIn("✅".encode("utf-8"), raw.getvalue())

    def test_unencodable_text_on_stderr_stays_readable(self):
        module = self.load_console()
        out, err = io.BytesIO(), io.BytesIO()
        stdout = io.TextIOWrapper(out, encoding="cp1251")
        stderr = io.TextIOWrapper(err, encoding="cp1251")
        with patch.object(sys, "stdout", stdout), patch.object(sys, "stderr", stderr):
            module.utf8_console()
            print("plugins/\udcff", file=sys.stderr)
            sys.stderr.flush()

        self.assertIn(b"plugins/\\udcff", err.getvalue())

    def run_converter(self, script: str, make_plugin) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            make_codex_marketplace(repo, [])
            plugin = make_plugin(repo, "sample")
            env = dict(os.environ, PYTHONIOENCODING="cp1251")
            return subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "scripts" / script), str(plugin), "--repo-root", str(repo)],
                capture_output=True,
                env=env,
            )

    def test_converters_run_by_the_installed_hook_survive_a_legacy_console(self):
        for script, make_plugin in (
            ("convert_cc_to_codex.py", make_cc_plugin),
            ("convert_codex_to_cc.py", make_codex_plugin),
        ):
            with self.subTest(script=script):
                result = self.run_converter(script, make_plugin)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                self.assertIn("✅".encode("utf-8"), result.stdout)


if __name__ == "__main__":
    unittest.main()
