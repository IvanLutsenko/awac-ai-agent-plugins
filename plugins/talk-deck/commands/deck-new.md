---
description: Start a talk deck with Craft — a themed deck for the nearest holiday, with the author's defaults and a Harold slide at the end.
argument-hint: "<talk topic> [--date YYYY-MM-DD] [--slug name]"
allowed-tools: Bash(source:*), Bash(bash:*), Bash(python3:*), Bash(mkdir:*), Bash(ls:*), Bash(date:*), Bash(open:*), Bash(git -C:*), Read, Write, Edit, Skill, AskUserQuestion
---

# /deck-new — start a themed talk deck

## Arguments

Parse `$ARGUMENTS`:
- `--date YYYY-MM-DD` — the talk date. Without it, ask once; the date picks the holiday.
- `--slug name` — the folder name. Without it, make a short Latin kebab-case slug from the topic.
- everything else — the talk topic.

No topic → stop and report `Usage: /deck-new <talk topic> [--date YYYY-MM-DD] [--slug name]`.

## 1. Settings and Craft

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh
echo "config=$(td_config_path)"
echo "author=$(td_author)"
echo "contact=$(td_contact)"
echo "lang=$(td_lang)"
echo "decks_dir=$(td_decks_dir)"
echo "craft=$(td_craft_home || echo MISSING)"
```

- `craft=MISSING` → stop: the Craft skill is required (`ln -s <craft clone> ~/.claude/skills/craft`).
- An empty `author`, `contact` or `decks_dir` → ask for them and write `~/.claude/talk-deck.local.md`:

```yaml
---
author: <name as on the cover>
contact: <one URL for the closing QR>
lang: ru
site_repo: <path to the site repo, decks go to its res/>
---
# talk-deck — user settings
```

The target is `<decks_dir>/<slug>`. If it exists and is not empty, stop and say so.

## 2. Scaffold

```bash
python3 "<craft>/scripts/scaffold.py" "<decks_dir>/<slug>" --surface slides --title "<title>" --author "<author>" --lang <lang>
```

Versions. If the deck folder is not inside another git repository (`git -C <deck> rev-parse` fails), run `git init` there and create an empty `.talk-deck` marker in the deck root, then commit the scaffold as `round 0: scaffold` in a separate command, never in one command with `git init` or a file edit. The marker tells the author's review gate that this is a local deck history, not code; a deck repo with a remote is gated as usual. A deck inside the site repo already has git: do nothing. Before every round of edits, commit `round N: <what changes>`; roll back with git, never by copying the folder (`d-1111-v2-before` and the like are what this replaces). A commit hook may refuse an agent commit (for example a review gate); then tell the author, and the round goes on uncommitted rather than around the hook.

## 3. Build with Craft

Invoke the `craft` skill and follow it for the slides branch. Hand it these facts so it does not ask again: the topic, the date, the deck folder, the language, the author, the contact. Then, inside the Craft workflow:

1. Theme: follow `references/slides/theme.md` — the holiday by the date, two or three samples, a fresh `deck-theme.css`, fonts through `scripts/fetch_font.py`. An emoji rain is optional; offer it only for a holiday.
2. Outline: `references/slides/narrative.md`. Draft the skeleton with real content from the author; mark gaps instead of inventing facts.
3. Closing: an `end` slide with `data-key="end"` and `QR_LINK` from `scripts/qr.py <contact> --link`. `/deck-harold` later swaps it for the `harold` layout once the picture exists.
4. Rehearsal timer: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/rehearse.sh <decks_dir>/<slug> [minutes]` with the talk length if the author gave it; see `/deck-rehearse`.

## 4. Check and report

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh
CHROMIUM="$(td_chromium)" python3 "$(td_craft_home)/scripts/check_project.py" "<decks_dir>/<slug>"
```

Fix what it reports. Open the deck with `open <deck>/index.html` and report: the folder, the chosen holiday and theme idea, the slide list, what is left (`/deck-harold`, content gaps).
