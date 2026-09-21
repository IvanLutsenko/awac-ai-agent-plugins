import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins/combined-review/scripts/filter-findings.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("filter_findings", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ParseFindingTest(unittest.TestCase):
    def setUp(self):
        self.parse = load_module().parse_finding

    def test_agent_bullet(self):
        p, l, s = self.parse("- [critical] src/foo.ts:42 - `getFx` has no `.fail` handler")
        self.assertEqual((p, l), ("src/foo.ts", "42"))
        self.assertEqual(s, "getFx")

    def test_numbered_report_line_with_backticks(self):
        p, l, _ = self.parse("1. `src/a/b.tsx:7` - description [source: code-reviewer]")
        self.assertEqual((p, l), ("src/a/b.tsx", "7"))

    def test_prose_number_is_not_an_anchor(self):
        self.assertIsNone(self.parse("Step 5:42 findings were collected"))

    def test_line_without_any_anchor(self):
        self.assertIsNone(self.parse("- everything looks fine"))


class FilterTest(unittest.TestCase):
    """End-to-end over real files: the point of the script is that a human can
    re-run it and get the same verdicts."""

    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src/foo.ts").write_text(
            "import x\n"
            "\n"
            "const url = '/app/service'\n"
            "export const getFx = createEffect(load)\n"
        )
        self.positions = self.root / "positions.txt"
        self.positions.write_text("src/foo.ts:3\nsrc/foo.ts:4\n")

    def run_on(self, findings):
        f = self.root / "findings.txt"
        f.write_text(findings)
        pairs, files = self.module.load_positions(self.positions)
        out = []
        for raw in findings.splitlines():
            if not raw.strip():
                continue
            parsed = self.module.parse_finding(raw)
            if not parsed:
                out.append(("unparsed", None))
                continue
            path, line, snippet = parsed
            if (path, line) in pairs:
                out.append(("keep", line))
            elif path in files:
                new, _ = self.module.reanchor(self.root, path, snippet, pairs)
                out.append(("moved", new) if new else ("drop", line))
            else:
                out.append(("drop", line))
        return out

    def test_line_in_the_map_is_kept(self):
        self.assertEqual(self.run_on("- [info] src/foo.ts:4 - effect"), [("keep", "4")])

    def test_wrong_line_is_reanchored_by_the_quoted_code(self):
        # 120 is a position inside the saved .diff, not a line of this 4-line file
        self.assertEqual(
            self.run_on("- [info] src/foo.ts:120 - `getFx` has no `.fail`"),
            [("moved", "4")],
        )

    def test_wrong_line_without_a_quote_is_dropped(self):
        self.assertEqual(self.run_on("- [info] src/foo.ts:120 - something"), [("drop", "120")])

    def test_quoted_code_on_an_untouched_line_is_dropped(self):
        self.assertEqual(self.run_on("- [info] src/foo.ts:120 - `import x` here"), [("drop", "120")])

    def test_untouched_file_is_dropped(self):
        self.assertEqual(self.run_on("- [info] src/other.ts:2 - `import x`"), [("drop", "2")])

    def test_unparsable_line_is_counted_not_swallowed(self):
        self.assertEqual(self.run_on("- everything looks fine"), [("unparsed", None)])


class EmptyMapTest(unittest.TestCase):
    def test_empty_position_map_stops_filtering(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as d:
            pos = Path(d) / "positions.txt"
            pos.write_text("")
            pairs, files = module.load_positions(pos)
            self.assertEqual((pairs, files), (set(), set()))


if __name__ == "__main__":
    unittest.main()
