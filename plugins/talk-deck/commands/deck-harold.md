---
description: Harold for a talk deck — brief the picture in the deck's theme through drawbridge, then place the downloaded image on the closing slide.
argument-hint: "[deck] | place [deck] [image]"
allowed-tools: Bash(source:*), Bash(bash:*), Bash(python3:*), Bash(pbcopy:*), Bash(open:*), Read, Edit, Skill
---

# /deck-harold — the closing Harold

Two steps, because the image is made in a web UI by the author:

1. `/deck-harold [deck]` — write the brief and hand it to drawbridge.
2. `/deck-harold place [deck] [image]` — take the downloaded picture and put it on the closing slide.

`deck` is a slug in the decks folder, a path, or empty for the current folder.

## Resolve the deck

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh
echo "deck=$(td_resolve_deck "<deck arg>" || echo MISSING)"
echo "craft=$(td_craft_home || echo MISSING)"
```

`MISSING` → stop and say which one.

## Step 1: brief

1. Read `<deck>/deck-theme.css` and the deck's cover: the occasion, palette, decor and mood.
2. Read the "Harold" section of `<craft>/references/slides/theme.md` and two `harold-prompt.txt` files from `<craft>/samples/` that are closest to this theme.
3. Write a new English brief in the same shape: the Hide the Pain Harold meme character with his strained smile; setting and costume from the occasion; the style and palette of this deck; the face in the middle with calm bands at the top and bottom; no text, letters or captions; aspect 4:3, at least 1600 px wide.
4. Hand it over: invoke drawbridge's draw skill with the brief (`drawbridge:draw` in Claude Code, `drawbridge-draw` in Codex). If drawbridge is not installed, copy the brief with `pbcopy` and print it.
5. Report the brief and the next step: generate, download the image, run `/deck-harold place`.

## Step 2: place

1. Store the picture:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/place-harold.sh "<deck>" [image]
```

Without an image it takes the newest picture in `~/Downloads`. Tell the author which file it took (the `source=` line) and pass on any warning. It shrinks only a picture wider than 2000 px and never enlarges one.

2. The closing slide. If `<deck>/index.html` has a `data-slide-layout="harold"` slide, point its `<img>` at the `stored=` path. Otherwise replace the `end` slide with the `harold` fragment from `<craft>/assets/slides/fragments/harold.html`, keeping `data-key`, the author and the `.qr-link` block of the old slide. The meme lines come from the deck language: Russian words are in `<craft>/references/russian.md`; the `alt` is a short description of the picture.
3. Check:

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh
CHROMIUM="$(td_chromium)" python3 "$(td_craft_home)/scripts/check_project.py" "<deck>"
```

Fix what it reports, then open the deck on the closing slide: `open "<deck>/index.html#<last page>"`.
