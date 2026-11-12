import ast
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((PLUGIN_ROOT / "scripts").glob("*.py"))


def calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


class PlatformNeutralOutputTest(unittest.TestCase):
    """Generated files are committed and compared byte for byte, so a run on Windows
    must write what a run on macOS or Linux writes: LF line ends, `/` in paths."""

    def test_every_write_text_pins_the_line_ending(self):
        missing = [
            f"{path.name}:{node.lineno}"
            for path in SCRIPTS
            for node in calls(path)
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "write_text"
            and not any(kw.arg == "newline" for kw in node.keywords)
        ]
        self.assertEqual(missing, [], "write_text without newline= writes CRLF on Windows")

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

    def test_report_survives_a_legacy_console_code_page(self):
        spec = importlib.util.spec_from_file_location(
            "cross_port_console", PLUGIN_ROOT / "scripts" / "cross_port.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1251")
        with patch.object(sys, "stdout", console), patch.object(sys, "stderr", console):
            module.utf8_console()
            print("  ✅ generated")
            sys.stdout.flush()

        self.assertIn("✅".encode("utf-8"), raw.getvalue())


if __name__ == "__main__":
    unittest.main()
