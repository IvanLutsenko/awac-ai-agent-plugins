---
description: Put a talk deck into Google Slides — the final frame of every slide as a full-bleed picture in a new presentation, for organizers who stitch several speakers into one Slides file.
argument-hint: "[deck] [--title name]"
allowed-tools: Bash(bash:*), Bash(source:*), Bash(ls:*), Read, Edit, AskUserQuestion, mcp__google-workspace-unlimited__check_drive_auth, mcp__google-workspace-unlimited__upload_to_drive, mcp__google-workspace-unlimited__create_presentation, mcp__google-workspace-unlimited__make_drive_files_public, mcp__google-workspace-unlimited__update_slide_content, mcp__google-workspace-unlimited__get_presentation_info, mcp__google-workspace-unlimited__manage_drive_files
---

# /deck-google-slides — the deck as a Google Slides presentation

What the organizer gets: one slide per deck slide, each a 1920×1080 picture of its final frame. Reveal steps, counters and decor motion do not survive; the organizer can add Slides animations and memes on top.

Requires the `google-workspace-unlimited` MCP server, authorized for the author's Google account.

**Privacy.** The Slides API inserts a picture only from a public URL. For the few seconds between upload and insertion every PNG is readable by anyone who has its link; right after insertion the PNGs are deleted for good, and the slides keep their own copies. For a corporate or unreleased deck that is the author's call: say it before uploading the first time and go on only with a yes.

## Arguments

Parse `$ARGUMENTS`: `deck` (a slug, a path, or empty for the current folder), `--title name` (default: the deck's `<title>`).

## 1. Account

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh
echo "config=$(td_config_path)"
echo "google_email=$(td_get google_email)"
```

No `google_email` → ask once for the Google account and add `google_email: <address>` to the frontmatter of the config file (`~/.claude/talk-deck.local.md` when there is none yet). Pass it as `user_google_email` in every call below. Run `check_drive_auth`; not authenticated → stop and tell the author to authorize the server (`start_google_auth`).

## 2. Frames

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/frames.sh <deck> "$(mktemp -d)/frames"
```

It prints `frames=<dir>` and `count=N`; the files are `NN-<key>.png` in slide order. Look at two or three of them before uploading: a broken frame in Slides is harder to notice than here.

## 3. Upload

`upload_to_drive` once per PNG, `path=<file>`, into the root. Collect each file id by its file name. Do not upload the folder: cleanup then deletes only ids this run created.

From here on, step 5 runs no matter what fails in between.

## 4. Presentation and pictures

1. `create_presentation` with the title. Keep `presentationId`. The new presentation is 16:9 (9144000×5143500 EMU) with one empty slide whose objectId is `p`.
2. `make_drive_files_public` on all PNG ids.
3. `update_slide_content` in batches of at most 20 slides, in file-name order. For slide number `n` (zero-padded to three digits, because Slides wants object ids of 5+ characters):

```json
{"createSlide": {"objectId": "page_NNN", "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
{"createImage": {"url": "https://drive.google.com/uc?export=download&id=<file id>",
  "elementProperties": {"pageObjectId": "page_NNN",
    "size": {"width": {"magnitude": 9144000, "unit": "EMU"}, "height": {"magnitude": 5143500, "unit": "EMU"}},
    "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "EMU"}}}}
```

4. One more `update_slide_content` with `{"deleteObject": {"objectId": "p"}}`.
5. `get_presentation_info`: the slide count must equal `count`, each slide with one image.

## 5. Clean up — always

`manage_drive_files` with `operation=delete`, `permanent=true` on every PNG id from step 3, and nothing else. Do it right after step 4, before the report, and also when any step after the upload failed. Report what was deleted; if a delete fails, give the author the file names and ids so they can remove them by hand — a leftover PNG stays public.

## 6. Report

The presentation link, the slide count, and that every slide is a picture: edits to the text go into the deck, then this command runs again.
