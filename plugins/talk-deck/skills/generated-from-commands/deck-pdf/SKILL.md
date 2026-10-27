---
name: talk-deck-deck-pdf
description: PDF of a talk deck for organizers — full Craft check, then a PDF with every reveal step or only the final frames. Use when the user invokes /deck-pdf.
version: 0.1.0
---

> Converted from Claude Code command `/deck-pdf`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.
> Helper scripts ship in this skill's own `scripts/` directory. Replace
> `<this skill directory>` with the path Codex reported when it loaded this skill —
> a bare relative path would resolve against the repository under review instead.

# /deck-pdf — a PDF for the organizers

Parse `$ARGUMENTS`:
- `deck` — a slug in the decks folder, a path, or empty for the current folder;
- `--final` — one page per slide in its final frame instead of a page per reveal step. Organizers who print or post slides usually want this;
- `--archive` — also keep the release ZIP, the offline deck for the venue computer.

Run, passing the arguments through:

```bash
bash <this skill directory>/scripts/pdf.sh <deck> [--final] [--archive]
```

The script runs the full Craft check first and stops on a failure: report what the check printed, do not work around it. The output goes to `~/Downloads/talk-deck/<slug>/`, outside the site repo, so it is never published by accident.

Report the `pdf=`, `pages=`, `size=` and `zip=` lines it prints, then `open` the output folder.
