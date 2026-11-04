---
name: talk-deck-deck-pdf
description: PDF of a talk deck for organizers — full Craft check, then a PDF with every reveal step or only the final frames, optionally straight into a repo with its share link. Use when the user invokes /deck-pdf.
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
- `--archive` — also keep the release ZIP, the offline deck for the venue computer;
- `--into dir` — final frames into `<dir>/<slug>.pdf` instead of `~/Downloads`. Use it to share the deck through a repo: a PDF in GitLab or GitHub opens in the browser for anyone with access, no hosting needed. Implies `--final`.

Run, passing the arguments through:

```bash
bash <this skill directory>/scripts/pdf.sh <deck> [--final] [--archive] [--into dir]
```

The script runs the full Craft check first and stops on a failure: report what the check printed, do not work around it. Without `--into` the output goes to `~/Downloads/talk-deck/<slug>/`, outside the site repo, so it is never published by accident.

Report the `pdf=`, `pages=`, `size=` and `zip=` lines it prints. With `--into` inside a GitLab or GitHub repo it also prints `link=`: the blob URL on the remote's default branch. That link works only after the author commits and pushes the PDF; say so, and do not commit or push yourself. Without `--into`, `open` the output folder.
