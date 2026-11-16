"""Tests for link-skills at the repository root. Run: python -m unittest discover -s scripts"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LINK_SKILLS = REPO / "link-skills"
SKILLS = sorted(path.parent.name for path in (REPO / "skills").glob("*/SKILL.md"))
AGENT_FOLDERS = {
    "claude-code": ".claude/skills",
    "codex": ".agents/skills",
    "cursor": ".cursor/skills",
    "opencode": ".config/opencode/skills",
    "hermes-agent": ".hermes/skills",
}


class LinksSkillsIntoAgents(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.home)

    def run_link_skills(self, *args, script=LINK_SKILLS, **env):
        environ = {"HOME": str(self.home), "PATH": os.environ["PATH"], **env}
        return subprocess.run([str(script), *args], env=environ, capture_output=True, text=True)

    def linked(self, folder):
        folder = self.home / folder
        if not folder.is_dir():
            return []
        return sorted(
            entry.name
            for entry in folder.iterdir()
            if entry.is_symlink() and entry.resolve() == (REPO / "skills" / entry.name).resolve()
        )

    def test_each_agent_gets_one_link_per_skill(self):
        for agent, folder in AGENT_FOLDERS.items():
            with self.subTest(agent):
                result = self.run_link_skills("--agent", agent)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.linked(folder), SKILLS)
                self.assertTrue(all((self.home / folder / name / "SKILL.md").is_file() for name in SKILLS))

    def test_short_agent_names_work(self):
        for short, agent in [("claude", "claude-code"), ("hermes", "hermes-agent")]:
            with self.subTest(short):
                result = self.run_link_skills("--agent", short)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.linked(AGENT_FOLDERS[agent]), SKILLS)

    def test_agent_folders_follow_their_environment_variables(self):
        env = {
            "claude-code": ("CLAUDE_CONFIG_DIR", "claude-config", "claude-config/skills"),
            "opencode": ("XDG_CONFIG_HOME", "xdg", "xdg/opencode/skills"),
            "hermes-agent": ("HERMES_HOME", "hermes-home", "hermes-home/skills"),
        }
        for agent, (variable, value, folder) in env.items():
            with self.subTest(agent):
                result = self.run_link_skills("--agent", agent, **{variable: str(self.home / value)})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.linked(folder), SKILLS)

    def test_without_an_agent_it_links_every_agent_it_finds(self):
        for home in [".cursor", ".hermes", ".codex"]:
            (self.home / home).mkdir()
        result = self.run_link_skills()
        self.assertEqual(result.returncode, 0, result.stderr)
        for agent in ["cursor", "hermes-agent", "codex"]:
            self.assertEqual(self.linked(AGENT_FOLDERS[agent]), SKILLS)
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".config").exists())

    def test_without_any_agent_it_stops(self):
        result = self.run_link_skills()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_running_again_changes_nothing(self):
        self.run_link_skills("--agent", "claude-code")
        result = self.run_link_skills("--agent", "claude-code")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"0 linked, 0 repointed, {len(SKILLS)} already linked", result.stdout)
        self.assertEqual(self.linked(AGENT_FOLDERS["claude-code"]), SKILLS)

    def test_an_old_link_is_repointed(self):
        old_skill = self.home / "old-clone" / "skills" / SKILLS[0]
        old_skill.mkdir(parents=True)
        folder = self.home / AGENT_FOLDERS["claude-code"]
        folder.mkdir(parents=True)
        (folder / SKILLS[0]).symlink_to(old_skill)
        result = self.run_link_skills("--agent", "claude-code")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 repointed", result.stdout)
        self.assertIn(f"{SKILLS[0]}: repointed from {old_skill}", result.stdout)
        self.assertEqual(self.linked(AGENT_FOLDERS["claude-code"]), SKILLS)
        self.assertEqual(list(old_skill.iterdir()), [])

    def test_links_to_removed_skills_are_cleaned_up(self):
        folder = self.home / AGENT_FOLDERS["claude-code"]
        folder.mkdir(parents=True)
        (folder / "venice-removed").symlink_to(REPO / "skills" / "venice-removed")
        (folder / "my-gone-skill").symlink_to(self.home / "elsewhere" / "my-gone-skill")
        result = self.run_link_skills("--agent", "claude-code")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 removed", result.stdout)
        self.assertFalse((folder / "venice-removed").is_symlink())
        self.assertTrue((folder / "my-gone-skill").is_symlink())
        self.assertEqual(self.linked(AGENT_FOLDERS["claude-code"]), SKILLS)

    def test_a_clone_reached_through_a_link_is_the_same_clone(self):
        (self.home / "clone-link").symlink_to(REPO)
        self.run_link_skills("--agent", "claude-code", script=self.home / "clone-link" / "link-skills")
        result = self.run_link_skills("--agent", "claude-code")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"0 linked, 0 repointed, {len(SKILLS)} already linked", result.stdout)

    def test_a_real_folder_is_left_alone(self):
        for args, folder in [
            (["--agent", "claude-code"], AGENT_FOLDERS["claude-code"]),
            (["--dir", str(self.home / "other-agent" / "skills")], "other-agent/skills"),
        ]:
            with self.subTest(args=args):
                own_copy = self.home / folder / SKILLS[0]
                own_copy.mkdir(parents=True)
                (own_copy / "SKILL.md").write_text("my edits", encoding="utf-8")
                result = self.run_link_skills(*args)
                self.assertEqual(result.returncode, 1)
                self.assertIn(str(own_copy), result.stderr)
                self.assertFalse(own_copy.is_symlink())
                self.assertEqual((own_copy / "SKILL.md").read_text(encoding="utf-8"), "my edits")
                self.assertEqual(self.linked(folder), SKILLS[1:])

    def test_dir_links_into_any_folder(self):
        result = self.run_link_skills("--dir", str(self.home / "other-agent" / "skills"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.linked("other-agent/skills"), SKILLS)

    def test_bad_arguments_change_nothing(self):
        both = ["--agent", "claude-code", "--dir", str(self.home / "other-agent")]
        for args in [["--agent", "vscode"], ["--agent"], ["--dir"], both, ["--force"]]:
            with self.subTest(args=args):
                result = self.run_link_skills(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(list(self.home.iterdir()), [])

    def test_it_needs_the_skills_folder_beside_it(self):
        elsewhere = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, elsewhere)
        shutil.copy2(LINK_SKILLS, elsewhere / "link-skills")
        result = self.run_link_skills("--agent", "claude-code", script=elsewhere / "link-skills")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
