---
description: Put a talk deck into Google Slides — 2x pictures of every slide or reveal step, counters as GIF overlays, and later updates in place so transitions and the organizer's copy survive.
argument-hint: "[deck] [--title name] [--steps] [--update] [--only key,key]"
allowed-tools: Bash(bash:*), Bash(source:*), Bash(ls:*), Bash(cat:*), Read, Write, Edit, AskUserQuestion, mcp__google-workspace-unlimited__check_drive_auth, mcp__google-workspace-unlimited__upload_to_drive, mcp__google-workspace-unlimited__create_presentation, mcp__google-workspace-unlimited__make_drive_files_public, mcp__google-workspace-unlimited__update_slide_content, mcp__google-workspace-unlimited__get_presentation_info, mcp__google-workspace-unlimited__manage_drive_files
---

# /deck-google-slides — the deck as a Google Slides presentation

What the organizer gets: one slide per deck slide, a 3840×2160 picture of its final frame. With `--steps`, one slide per reveal step, so clicking through Slides reveals the deck the way the talk does; a step that counts (`data-count`) or is marked `data-gif` also gets a GIF of its motion over the picture. Decor motion does not survive: a deck may keep static decor for Slides in `gslides.css` next to `index.html`, applied only to these frames, so the finished deck stays untouched.

Requires the `google-workspace-unlimited` MCP server, authorized for the author's Google account.

**Privacy.** The Slides API inserts a picture only from a public URL. For the few seconds between upload and insertion every file is readable by anyone who has its link; right after insertion the files are deleted for good, and the slides keep their own copies (an organizer's copy of the slides keeps them too). For a corporate or unreleased deck that is the author's call: say it before uploading the first time and go on only with a yes.

## Arguments

Parse `$ARGUMENTS`: `deck` (a slug, a path, or empty for the current folder), `--title name` (default: the deck's `<title>`), `--steps` (every reveal step as its own slide), `--update` (replace the pictures in the presentation from `<deck>/gslides.json` instead of creating a new one), `--only key,key` (with `--update`: only these deck slides, for a quick fix such as a new QR code).

## 1. Account

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh
echo "config=$(td_config_path)"
echo "google_email=$(td_get google_email)"
```

No `google_email` → ask once for the Google account and add `google_email: <address>` to the frontmatter of the config file (`~/.claude/talk-deck.local.md` when there is none yet). Pass it as `user_google_email` in every call below. Run `check_drive_auth`; not authenticated → run `start_google_auth` for that account and wait for the author to finish it in the browser. Authorization expires between sessions, so expect this on a later run too.

## 2. Frames

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/slides-frames.sh <deck> "$(mktemp -d)/frames" [--steps] [--only key,key]
```

It prints `frames=<dir>`, `count=` (pictures written), `gifs=` and `slides=` (slides the presentation must have), and writes `frames.json`: the deck `background` color, the GIF `overlay` box in EMU, `map` (every slide of the presentation in order as `key/step`), and per frame its slide number `n`, `png` and `gif` (or null). Look at two or three PNGs and one GIF before uploading: a broken frame in Slides is harder to notice than here.

## 3. Upload

`upload_to_drive` once per file in `frames.json` (PNG and GIF), `path=<file>`, into the root, then `make_drive_files_public` on all ids. Collect each id by file name. Do not upload the folder: cleanup then deletes only ids this run created.

From here on, step 6 runs no matter what fails in between.

`URL(id)` below is `https://drive.google.com/uc?export=download&id=<id>`. Object ids follow templates (`%03d` is the slide number `n`): `slide_%03d`, `frame_%03d`, `anim_%03d` for a new presentation; with `--update`, the templates from `gslides.json`.

## 4a. New presentation

1. `create_presentation` with the title. Keep `presentationId`. The new presentation is 16:9 (9144000×5143500 EMU) with one empty slide `p`.
2. `update_slide_content` in batches of at most 20 slides, in `n` order. Per frame:

```json
{"createSlide": {"objectId": "slide_NNN", "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
{"updatePageProperties": {"objectId": "slide_NNN", "fields": "pageBackgroundFill",
  "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": <background as 0–1 red/green/blue>}}}}}},
{"createImage": {"objectId": "frame_NNN", "url": "URL(png id)",
  "elementProperties": {"pageObjectId": "slide_NNN",
    "size": {"width": {"magnitude": 9144000, "unit": "EMU"}, "height": {"magnitude": 5143500, "unit": "EMU"}},
    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "EMU"}}}}
```

   and, when the frame has a GIF, one more `createImage` with `objectId` `anim_NNN`, the GIF's URL, `size` from `overlay.width`/`overlay.height` and `translateX`/`translateY` from `overlay.x`/`overlay.y`. The background in the deck's color keeps a transition from flashing white between slides.
3. `update_slide_content` with `{"deleteObject": {"objectId": "p"}}`.
4. Write `<deck>/gslides.json`: `{"presentation": "<id>", "slide": "slide_%03d", "frame": "frame_%03d", "anim": "anim_%03d", "map": <map from frames.json>, "anims": [<n of every frame with a GIF>]}`. It is export state, not deck content: the release leaves it out.

## 4b. Update in place (`--update`)

Read `<deck>/gslides.json`; none → stop and run without `--update`. Its `map` must equal the `map` in `frames.json`; any difference means slides were added, removed or reordered, and replacing pictures would put them under the wrong transitions and notes: stop and offer a new presentation. A `gslides.json` without `map` (an older one) → compare `slides` with `slides=` and tell the author that order is not checked.

Per frame, in one `update_slide_content` (batches of at most 40 requests):
- `{"replaceImage": {"imageObjectId": "<frame id>", "url": "URL(png id)", "imageReplaceMethod": "CENTER_CROP"}}`;
- a GIF and `n` in `anims` → `replaceImage` on the anim id; a GIF and `n` not in `anims` → `createImage` as in 4a; no GIF and `n` in `anims` → `deleteObject` on the anim id.

Then update `anims` in `gslides.json`. Slides, their order, transitions and speaker notes stay as they were.

## 5. Check

`get_presentation_info`: the slide count equals `slides=`.

## 6. Clean up — always

`manage_drive_files` with `operation=delete`, `permanent=true` on every id from step 3, and nothing else. Do it right after step 4, before the report, and also when any step after the upload failed. Report what was deleted; if a delete fails, give the author the file names and ids so they can remove them by hand — a leftover file stays public.

## 7. Report

The presentation link and the slide count, then what the API cannot do and the author should know:
- **Transitions** are set by hand: Slide → Transition → Dissolve, 0.2–0.3 s → Apply to all slides. Without one, the slides cut.
- **GIFs play only in a plain slideshow.** Presenter view previews the next slide in the same browser tab, and a GIF plays once per tab: it runs in the preview and the audience gets its last frame. A Drive video with autoplay does not help either: it plays in the presenter window, not on the main screen. The last frame is the slide's final state, so nothing breaks; for live counters, present the HTML deck from the author's laptop.
- Every slide is a picture: edits go into the deck, then `/deck-google-slides --update` (with `--only` for one or two slides).
