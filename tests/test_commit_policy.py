import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / ".github/scripts/check_commits.py"


class CommitPolicy(unittest.TestCase):
    def check(self, subject, title=None):
        with tempfile.TemporaryDirectory() as root:
            subprocess.run(["git", "init", "-q", root], check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "commit", "-q", "--allow-empty", "-m", subject], cwd=root, check=True)
            env = dict(os.environ)
            env.pop("GITHUB_EVENT_PATH", None)
            if title is not None:
                sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
                event = Path(root) / "event.json"
                event.write_text(json.dumps({"pull_request": {
                    "title": title, "base": {"sha": sha}, "head": {"sha": sha}}}))
                env["GITHUB_EVENT_PATH"] = str(event)
            return subprocess.run([sys.executable, str(CHECKER)], cwd=root, env=env,
                                  capture_output=True, text=True)

    def test_conventional_commit_is_accepted(self):
        self.assertEqual(self.check("fix(terminal): preserve window size").returncode, 0)

    def test_nonconventional_commit_is_rejected(self):
        self.assertEqual(self.check("update files").returncode, 1)

    def test_breaking_change_pr_title_is_accepted(self):
        self.assertEqual(self.check("ci: test", "feat(api)!: change font selection").returncode, 0)

    def test_invalid_pr_title_is_rejected(self):
        self.assertEqual(self.check("ci: test", "please merge this").returncode, 1)
