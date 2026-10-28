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
