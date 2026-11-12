import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "plugins" / "android-verify" / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DUMP = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[0,0][1080,2400]">
    <node index="0" text="Amount" resource-id="com.example:id/amount" class="android.widget.EditText" content-desc="" clickable="true" bounds="[48,300][1032,420]" />
    <node index="1" text="" resource-id="" class="android.widget.ImageButton" content-desc="Back" clickable="true" bounds="[0,100][120,220]" />
    <node index="2" text="Настройки экрана" resource-id="" class="android.widget.TextView" content-desc="" clickable="false" bounds="[48,240][600,290]" />
    <node index="3" text="" resource-id="" class="android.view.View" content-desc="" clickable="false" bounds="[0,0][1080,10]" />
    <node index="4" text="Hidden" resource-id="" class="android.view.View" content-desc="" clickable="false" bounds="[10,10][10,10]" />
  </node>
</hierarchy>
"""


class UiNodesTest(unittest.TestCase):
    def setUp(self):
        self.module = load("ui-nodes")
        self.tmp = tempfile.TemporaryDirectory()
        self.dump = Path(self.tmp.name) / "ui.xml"
        self.dump.write_text(DUMP, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        out = StringIO()
        with redirect_stdout(out):
            code = self.module.main([str(self.dump), *args])
        return code, out.getvalue()

    def test_lists_readable_and_tappable_nodes_with_their_centre(self):
        found = self.module.nodes(DUMP)
        self.assertEqual(
            [(n["x"], n["y"], n["clickable"]) for n in found],
            [(540, 360, True), (60, 160, True), (324, 265, False)],
        )

    def test_skips_empty_and_zero_size_nodes(self):
        texts = [n["text"] for n in self.module.nodes(DUMP)]
        self.assertNotIn("Hidden", texts)
        self.assertEqual(len(texts), 3)

    def test_find_matches_text_description_and_id_case_insensitively(self):
        code, out = self.run_main("--find", "back")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), '60,160  tap  desc="Back"')
        code, out = self.run_main("--find", "AMOUNT")
        self.assertIn("540,360", out)

    def test_non_ascii_text_survives(self):
        code, out = self.run_main("--find", "настройки")
        self.assertEqual(code, 0)
        self.assertIn("Настройки экрана", out)

    def test_json_output(self):
        code, out = self.run_main("--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]["id"], "com.example:id/amount")

    def test_nothing_found_exits_1(self):
        code, _ = self.run_main("--find", "no such label")
        self.assertEqual(code, 1)

    def test_unreadable_dump_exits_2(self):
        self.dump.write_text("<hierarchy><node", encoding="utf-8")
        code, _ = self.run_main()
        self.assertEqual(code, 2)


FAILED_LOG = """> Task :app:compileDebugKotlin FAILED
e: file:///src/app/src/main/java/com/example/Foo.kt:42:13 Unresolved reference: bar

FAILURE: Build failed with an exception.

* What went wrong:
Execution failed for task ':app:compileDebugKotlin'.
> Compilation error. See log for more details

* Try:
> Run with --stacktrace option to get the stack trace.

BUILD FAILED in 12s
"""

TEST_LOG = """> Task :core:testDebugUnitTest

com.example.FooTest > returns empty list when nothing stored FAILED
    org.opentest4j.AssertionFailedError at FooTest.kt:31

> Task :core:testDebugUnitTest FAILED

BUILD FAILED in 40s
"""


class GradleSummaryTest(unittest.TestCase):
    def setUp(self):
        self.module = load("gradle-summary")
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "gradle.log"

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, text, newline="\n"):
        self.log.write_bytes(text.replace("\n", newline).encode("utf-8"))
        out = StringIO()
        with redirect_stdout(out):
            code = self.module.main([str(self.log)])
        return code, out.getvalue()

    def test_success(self):
        code, out = self.run_main("> Task :app:assembleDebug\n\nBUILD SUCCESSFUL in 1m 3s\n57 actionable tasks\n")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("BUILD SUCCESSFUL in 1m 3s"))

    def test_compile_failure_names_task_error_and_reason(self):
        code, out = self.run_main(FAILED_LOG)
        self.assertEqual(code, 1)
        self.assertIn(":app:compileDebugKotlin", out)
        self.assertIn("Foo.kt:42:13 Unresolved reference: bar", out)
        self.assertIn("Execution failed for task ':app:compileDebugKotlin'.", out)
        self.assertNotIn("--stacktrace", out)

    def test_failed_test_is_listed(self):
        code, out = self.run_main(TEST_LOG)
        self.assertEqual(code, 1)
        self.assertIn("com.example.FooTest > returns empty list when nothing stored", out)
        self.assertIn(":core:testDebugUnitTest", out)

    def test_crlf_log_from_windows(self):
        code, out = self.run_main(FAILED_LOG, newline="\r\n")
        self.assertEqual(code, 1)
        self.assertIn("Foo.kt:42:13", out)

    def test_no_result_line_exits_2(self):
        code, out = self.run_main("> Task :app:preBuild UP-TO-DATE\n")
        self.assertEqual(code, 2)
        self.assertIn("no BUILD result line", out)

    def test_last_result_wins_in_an_appended_log(self):
        code, _ = self.run_main(FAILED_LOG + "\nBUILD SUCCESSFUL in 9s\n")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
