# Contributing

Issues and pull requests are welcome. New terminal integrations, better font discovery, and usability fixes are especially useful.

For a bug report, include your OS, terminal and Herdr versions, what you tried, and what happened. Remove private information from screenshots and logs.

For a new terminal adapter, explain how fonts are applied, which windows or sessions are affected, how undo works, and whether a reload is needed. Include tests and update the terminal support notes. Say which behavior you tested live.

To work locally:

```sh
git clone https://github.com/ernsahin/herdr-fonts.git
cd herdr-fonts
herdr plugin link "$PWD"
python3 -m unittest discover -s tests -v
```

Keep PRs focused. For larger changes, open an issue first so we can agree on the approach. Contributions are accepted under the project's MIT license.

## Commits and pull requests

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for commit subjects and PR titles:

```text
feat(kitty): add live font reload
fix(terminal): preserve window dimensions
docs: clarify the keyboard shortcut
ci: test supported Python versions
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`. Scope is optional; add `!` before the colon for a breaking change.

Open a branch and submit a PR to `main`. CI checks new commits, the PR title, Python 3.9/3.13 on Linux, and Python 3.13 on macOS. All required checks must pass, review conversations must be resolved, and the repository owner (@ernsahin) must approve before merging. New commits dismiss previous approvals. PRs are squash-merged using the PR title as the final commit subject.
