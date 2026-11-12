"""codex-smoke.py: the static half - what an installed plugin must look like to work outside this repo."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/codex-smoke.py"
spec = importlib.util.spec_from_file_location("codex_smoke", SCRIPT_PATH)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

HEAD = "---\nname: {name}\ndescription: Does a thing: with a colon.\n---\n"


class CheckInstalledTest(unittest.TestCase):
    def installed(self, skills):
        """skills: {dir: (name, body, [helper files])} -> (fails, warns, names)."""
        with tempfile.TemporaryDirectory() as d:
            for folder, (name, body, helpers) in skills.items():
                skill = Path(d) / "skills" / folder
                (skill / "scripts").mkdir(parents=True)
                (skill / "SKILL.md").write_text((HEAD.format(name=name) if name else "") + body)
                for h in helpers:
                    (skill / "scripts" / h).write_text("")
            return M.check_installed("demo", Path(d))

    def test_self_contained_skill_is_clean(self):
        body = 'python3 "<this skill directory>/scripts/run.py" plan\n'
        self.assertEqual(self.installed({"a": ("demo-a", body, ["run.py"])}), ([], [], ["demo-a"]))

    def test_helper_not_shipped_fails(self):
        fails, _, _ = self.installed({"a": ("demo-a", '"<this skill directory>/scripts/run.py"', [])})
        self.assertIn("scripts/run.py", fails[0])

    def test_plugin_root_path_fails_but_a_mention_does_not(self):
        fails, _, _ = self.installed({"a": ("demo-a", "read ${CLAUDE_PLUGIN_ROOT}/commands/x.md", [])})
        self.assertEqual(len(fails), 1)
        fails, _, _ = self.installed({"a": ("demo-a", "the converter rewrites `${CLAUDE_PLUGIN_ROOT}` paths", [])})
        self.assertEqual(fails, [])

    def test_plugin_root_with_a_default_is_still_a_path(self):
        """What auto-theme ships: Codex sets neither variable, so this runs /sync-theme.sh."""
        body = 'bash "${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT}}/sync-theme.sh"'
        self.assertEqual(len(self.installed({"a": ("demo-a", body, [])})[0]), 1)

    def test_quoted_name_is_read_without_the_quotes(self):
        with tempfile.TemporaryDirectory() as d:
            skill = Path(d) / "skills/a"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text('---\nname: "demo-a"\ndescription: \'x\'\n---\nbody')
            self.assertEqual(M.check_installed("demo", Path(d))[2], ["demo-a"])

    def test_another_plugins_repo_path_is_a_warning_too(self):
        _, warns, _ = self.installed({"a": ("demo-a", "python3 plugins/other/scripts/run.py", [])})
        self.assertEqual(len(warns), 1)

    def test_repo_relative_path_is_a_warning(self):
        fails, warns, _ = self.installed({"a": ("demo-a", "read plugins/demo/commands/x.md", [])})
        self.assertEqual((fails, len(warns)), ([], 1))

    def test_no_frontmatter_and_duplicate_names_fail(self):
        fails, _, _ = self.installed({"a": (None, "body", [])})
        self.assertTrue(any("frontmatter" in f for f in fails))
        fails, _, _ = self.installed({"a": ("same", "x", []), "b": ("same", "y", [])})
        self.assertTrue(any("declared 2 times" in f for f in fails))

    def test_plugin_without_skills_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(M.check_installed("demo", Path(d))[0], ["ships no skills"])


class ParseOfferedTest(unittest.TestCase):
    def test_skills_are_read_from_the_escaped_prompt(self):
        """`codex debug prompt-input` prints JSON: the list's newlines arrive as backslash-n."""
        prompt = (r'{"text":"## Skills\n- demo:demo-a: Does a thing: with a colon. (file: r1/a/SKILL.md)'
                  r'\n- demo:source-command-a: Migrated. (file: r1/b/SKILL.md)\n- other:x: X. (file: r2/SKILL.md)\n"}')
        self.assertEqual(M.parse_offered(prompt), {"demo": {"demo-a", "source-command-a"}, "other": {"x"}})

    def test_nothing_offered(self):
        self.assertEqual(M.parse_offered('{"text":"no skills here"}'), {})


if __name__ == "__main__":
    unittest.main()
