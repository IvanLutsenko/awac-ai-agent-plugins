---
description: PDF of a talk deck for organizers — full Craft check, then a PDF with every reveal step or only the final frames, optionally straight into a repo with its share link.
argument-hint: "[deck] [--final] [--archive] [--into dir]"
allowed-tools: Bash(bash:*), Bash(open:*), Read
---

# /deck-pdf — a PDF for the organizers

Parse `$ARGUMENTS`:
- `deck` — a slug in the decks folder, a path, or empty for the current folder;
- `--final` — one page per slide in its final frame instead of a page per reveal step. Organizers who print or post slides usually want this;
- `--archive` — also keep the release ZIP, the offline deck for the venue computer;
- `--into dir` — final frames into `<dir>/<slug>.pdf` instead of `~/Downloads`. Use it to share the deck through a repo: a PDF in GitLab or GitHub opens in the browser for anyone with access, no hosting needed. Implies `--final`.

Run, passing the arguments through:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/pdf.sh <deck> [--final] [--archive] [--into dir]
```

The script runs the full Craft check first and stops on a failure: report what the check printed, do not work around it. Without `--into` the output goes to `~/Downloads/talk-deck/<slug>/`, outside the site repo, so it is never published by accident.

Report the `pdf=`, `pages=`, `size=` and `zip=` lines it prints. With `--into` inside a GitLab or GitHub repo it also prints `link=`: the blob URL on the remote's default branch. That link works only after the author commits and pushes the PDF; say so, and do not commit or push yourself. Without `--into`, `open` the output folder.
