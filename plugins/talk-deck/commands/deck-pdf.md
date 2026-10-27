---
description: PDF of a talk deck for organizers — full Craft check, then a PDF with every reveal step or only the final frames.
argument-hint: "[deck] [--final] [--archive]"
allowed-tools: Bash(bash:*), Bash(open:*), Read
---

# /deck-pdf — a PDF for the organizers

Parse `$ARGUMENTS`:
- `deck` — a slug in the decks folder, a path, or empty for the current folder;
- `--final` — one page per slide in its final frame instead of a page per reveal step. Organizers who print or post slides usually want this;
- `--archive` — also keep the release ZIP, the offline deck for the venue computer.

Run, passing the arguments through:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/pdf.sh <deck> [--final] [--archive]
```

The script runs the full Craft check first and stops on a failure: report what the check printed, do not work around it. The output goes to `~/Downloads/talk-deck/<slug>/`, outside the site repo, so it is never published by accident.

Report the `pdf=`, `pages=`, `size=` and `zip=` lines it prints, then `open` the output folder.
