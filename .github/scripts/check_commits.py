"""Validate new commit subjects and PR titles without interpolating user input in shell."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PATTERN = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^()\r\n]+\))?!?: \S[^\r\n]*$")


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event = json.loads(Path(event_path).read_text()) if event_path else {}
    subjects = []
    if "pull_request" in event:
        pr = event["pull_request"]
        subjects.append(("PR title", pr["title"]))
        revisions = [f"{pr['base']['sha']}..{pr['head']['sha']}"]
    else:
        revisions = ["-1", "HEAD"]
    messages = subprocess.check_output(["git", "log", "--format=%s%x00", *revisions], text=True)
    subjects.extend(("Commit", text.strip()) for text in messages.split("\0") if text.strip())
    invalid = [(kind, subject) for kind, subject in subjects if not PATTERN.fullmatch(subject)]
    for kind, subject in invalid:
        print(f"{kind} must follow Conventional Commits: {subject!r}", file=sys.stderr)
    if invalid:
        print("Example: fix(terminal): preserve window dimensions", file=sys.stderr)
        return 1
    print(f"Validated {len(subjects)} Conventional Commits subjects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
