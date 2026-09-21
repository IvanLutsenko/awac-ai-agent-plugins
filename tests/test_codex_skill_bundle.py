"""The Codex port must be able to find its own helper scripts.

`${CLAUDE_PLUGIN_ROOT}` resolves to the installed plugin in Claude Code, so a
helper is reachable from any repository. Codex has no such variable: a
repo-relative path only resolves when Codex happens to run inside this
marketplace, which for a review tool acting on *another* repo never happens.
Codex proved it — `python3 plugins/combined-review/scripts/filter-findings.py`
came back `No such file or directory`. So the scripts ship inside the skill.
"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugins/combined-review"
GENERATED = PLUGIN / "skills/generated-from-commands"


def skills_with_scripts():
    return [d for d in sorted(GENERATED.iterdir()) if (d / "scripts").is_dir()]


class CodexSkillPathsTest(unittest.TestCase):
    def test_at_least_one_skill_bundles_scripts(self):
        self.assertTrue(skills_with_scripts(), "no generated skill carries scripts/ - rerun the converter")

    def test_no_unresolved_plugin_root_variable(self):
        for skill in sorted(GENERATED.glob("*/SKILL.md")):
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill.read_text(), skill.name)

    def test_no_marketplace_relative_script_paths(self):
        """The path Codex actually failed on."""
        for skill in sorted(GENERATED.glob("*/SKILL.md")):
            self.assertNotIn("plugins/combined-review/scripts/", skill.read_text(), skill.name)

    def test_referenced_helpers_exist_next_to_the_skill(self):
        for skill_dir in skills_with_scripts():
            text = (skill_dir / "SKILL.md").read_text()
            for line in text.splitlines():
                if "<this skill directory>/scripts/" not in line:
                    continue
                name = line.split("<this skill directory>/scripts/", 1)[1].split('"')[0].strip()
                self.assertTrue(
                    (skill_dir / "scripts" / name).is_file(),
                    f"{skill_dir.name} refers to scripts/{name}, which is not bundled",
                )

    def test_bundled_copy_matches_the_source(self):
        """A stale helper is worse than a missing one: it runs and looks right."""
        for skill_dir in skills_with_scripts():
            for copy in sorted((skill_dir / "scripts").iterdir()):
                source = PLUGIN / "scripts" / copy.name
                self.assertTrue(source.is_file(), f"{copy.name} has no source in the plugin")
                self.assertEqual(source.read_bytes(), copy.read_bytes(), copy.name)


if __name__ == "__main__":
    unittest.main()
