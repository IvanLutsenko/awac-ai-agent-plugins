# talk-deck

Talk decks on top of the [Craft](https://github.com/IvanLutsenko/craft) skill: a fresh holiday theme per talk, the author's defaults, a themed Harold on the closing slide, a PDF for organizers or a repo, a Google Slides copy, a roast by every agent and a card on the author's site. The plugin holds only commands and a hook; the design system, the samples and the checks stay in Craft.

Version: 0.5.0

## What's New in 0.5.0

Lessons from shipping a deck to Kolesa AI Meetup:
- `/deck-google-slides` renders frames at 2x through Chromium (1x looked soft on the projector), puts counting steps as GIF overlays recorded on the page's own clock, applies static decor from the deck's `gslides.css` without touching the deck, and gives every slide the deck's background so transitions do not flash white.
- `/deck-google-slides --update [--only key,key]` replaces pictures in the existing presentation from `<deck>/gslides.json`: slides, transitions and the organizer's copy stay as they are.
- The report says what Slides cannot do: transitions are set by hand, and GIFs play only in a plain slideshow, since presenter view plays them in its preview (a Drive video does not help either).
- `/deck-publish --hidden [--slug name]` releases a deck kept outside the site repo into `res/<slug>` with `noindex` and no card; a hidden deck stays hidden on re-publish.
- `/deck-rehearse`: press `Home` before `R` for a full run.

## 0.4.0

- `/deck-rehearse`: a stopwatch button in the deck's controls panel (`R`). A run times every slide against a plan from the talk length, records the voice, and ends with a table «слайд / факт / план / Δ», a JSON and the recording in Downloads. `/deck-rehearse analyze` transcribes the run locally with whisper and reviews the delivery slide by slide: overruns, what was and was not said, pace, filler words. `/deck-new` attaches it to a new deck.

## 0.3.0

- `/deck-google-slides --steps`: every reveal step as its own slide, so clicking through Slides reveals the deck the way the talk does.
- `/deck-new` puts a deck outside any repo under its own git and commits the scaffold; each round of edits is a commit `round N: <what>`, not a copy of the folder.
- `/deck-harold place` looks the picture over for generator defects first: fingers, handles and straps, stray letters, extra faces.

## 0.2.0

- `/deck-google-slides`: every slide's final frame as a full-bleed 1920×1080 picture in a new Google Slides presentation, for organizers who stitch speakers into one file.
- `/deck-review`: a roast by codex, pi and claude through `auto-handoff` plus a Claude Design reviewer, on a PDF, every screenshot and the sources the talk is about; factual claims are checked against the sources first.
- `/deck-pdf --into <dir>`: final frames into a folder, usually a repo; inside a GitLab or GitHub repo it prints the blob link on the default branch.

## 0.1.0

- First release: `/deck-new`, `/deck-harold`, `/deck-pdf`, `/deck-publish` and a static check after every edit inside a deck.

## Requirements

- The Craft skill, found in `craft_home` from the settings, `$CRAFT_HOME`, `~/.claude/skills/craft`, `~/.agents/skills/craft`, `~/.codex/skills/craft` or `~/projects/craft`.
- Python 3, Node.js 22+ and Chromium or Google Chrome for the Craft checks; `qrencode` and `zbar` for QR codes.
- Optional: the `drawbridge` plugin for the Harold brief, `cwebp` to store Harold as WebP.
- `/deck-review`: `pdftoppm` (`brew install poppler`) for the frames. `/deck-google-slides`: `ffmpeg` for the GIFs and the `google-workspace-unlimited` MCP server; `/deck-review` uses the `auto-handoff` skill when it is installed.
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
google_email:                # /deck-google-slides account, asked on first use
---
```

## Commands

```bash
/deck-new CI/CD in a bank --date 2026-12-20     # scaffold, holiday theme, outline, closing slide
/deck-harold                                    # brief for the themed Harold, sent to drawbridge
/deck-harold place                              # newest picture from ~/Downloads onto the closing slide
/deck-pdf --final                               # full check, one PDF page per slide, to ~/Downloads/talk-deck/<slug>
/deck-pdf --archive                             # a page per reveal step, plus the offline ZIP for the venue
/deck-pdf --into docs/deck                      # final frames into a repo folder, plus the blob link it gets once pushed
/deck-google-slides                             # a new Google Slides file, one picture per slide
/deck-google-slides --steps                     # one picture per reveal step, click through like the deck
/deck-google-slides --update --only about       # replace one slide's pictures in place, transitions kept
/deck-review                                    # roast by every agent: facts, story, slides, visuals
/deck-rehearse 22                               # rehearsal timer in the controls panel, 22-minute plan
/deck-rehearse analyze                          # newest run: transcript per slide, overruns, pace, fillers
/deck-publish --event "Podlodka #17"            # full check, cover, a card on the site in every language
/deck-publish --hidden --slug my-talk           # a deck kept elsewhere, by link only: noindex, no card
```

A deck outside a repo gets its own git: commit `round N: <what>` before each round of edits and roll back with git instead of copying the folder. The deck root holds an empty `.talk-deck` marker: a review gate can skip repos with the marker and no remote, since this is a deck's history, not code. A commit hook that still refuses an agent commit is the author's call, not something to work around. A new deck closes with an `end` slide; `/deck-harold place` swaps it for the `harold` layout once the picture exists. `/deck-publish` never commits or pushes the site.

`/deck-google-slides` is pictures: reveal steps with `--steps`, counters as GIFs that play only in a plain slideshow, never in presenter view. Edits go into the deck, then `--update`. Static decor for Slides goes into the deck's `gslides.css`; `gslides.json` keeps the presentation id and object ids for updates. The Slides API inserts a picture only from a public URL, so the files are link-readable for the seconds between upload and insertion and then deleted for good; for a corporate deck that is the author's call.

`/deck-rehearse` adds `rehearsal.js` to the deck. `R` or the stopwatch button starts and stops a run, `P` shows the last table. The plan is `data-talk-minutes` on `.deck` shared by reveal steps; `data-plan="<seconds>"` on a slide fixes its share. The script is inert until pressed, so it can stay in the published deck. The recording stays local: `analyze` needs `mlx-whisper` on Apple Silicon or `openai-whisper` (`uv tool install …`); the first run downloads the model.

## Hook

After `Edit`, `Write` or `MultiEdit` on a file inside a deck (a folder with `index.html` and `deck-theme.css`), the hook runs `check_project.py --static-only`, about a second. A failure goes back to the agent. Codex has no hook; its command skills run the checks themselves.
