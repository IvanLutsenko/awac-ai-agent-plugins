# talk-deck

Talk decks on top of the [Craft](https://github.com/IvanLutsenko/craft) skill: a fresh holiday theme per talk, the author's defaults, a themed Harold on the closing slide, a PDF for organizers and a card on the author's site. The plugin holds only commands and a hook; the design system, the samples and the checks stay in Craft.

Version: 0.1.0

## What's New in 0.1.0

- First release: `/deck-new`, `/deck-harold`, `/deck-pdf`, `/deck-publish` and a static check after every edit inside a deck.

## Requirements

- The Craft skill, found in `craft_home` from the settings, `$CRAFT_HOME`, `~/.claude/skills/craft`, `~/.agents/skills/craft`, `~/.codex/skills/craft` or `~/projects/craft`.
- Python 3, Node.js 22+ and Chromium or Google Chrome for the Craft checks; `qrencode` and `zbar` for QR codes.
- Optional: the `drawbridge` plugin for the Harold brief, `cwebp` to store Harold as WebP.
- macOS: the Harold step reads `~/Downloads` and uses `sips`.

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install talk-deck
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add talk-deck@awac-ai-agent-plugins
```

## Settings

YAML frontmatter of `~/.claude/talk-deck.local.md` (project-local override: `.claude/talk-deck.local.md`). `/deck-new` asks for the missing keys and writes the file.

```yaml
---
author: Ivan Lutsenko        # cover and closing byline
contact: https://t.me/name   # the one QR on the closing slide
lang: ru                     # deck language
site_repo: ~/site            # decks go to <site_repo>/res/<slug>
decks_dir:                   # optional, overrides <site_repo>/res
craft_home:                  # optional, path to the Craft skill
---
```

## Commands

```bash
/deck-new CI/CD in a bank --date 2026-12-20     # scaffold, holiday theme, outline, closing slide
/deck-harold                                    # brief for the themed Harold, sent to drawbridge
/deck-harold place                              # newest picture from ~/Downloads onto the closing slide
/deck-pdf --final                               # full check, one PDF page per slide, to ~/Downloads/talk-deck/<slug>
/deck-pdf --archive                             # a page per reveal step, plus the offline ZIP for the venue
/deck-publish --event "Podlodka #17"            # full check, cover, a card on the site in every language
```

A new deck closes with an `end` slide; `/deck-harold place` swaps it for the `harold` layout once the picture exists. `/deck-publish` never commits or pushes the site.

## Hook

After `Edit`, `Write` or `MultiEdit` on a file inside a deck (a folder with `index.html` and `deck-theme.css`), the hook runs `check_project.py --static-only`, about a second. A failure goes back to the agent. Codex has no hook; its command skills run the checks themselves.
