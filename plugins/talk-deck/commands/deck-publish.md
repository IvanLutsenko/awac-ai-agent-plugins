---
description: Publish a talk deck on the author's site — full Craft check, cover image, a presentation card in every site language. No commit or push.
argument-hint: "[deck] [--event name] [--video youtube-id]"
allowed-tools: Bash(bash:*), Bash(git -C:*), Bash(open:*), Read, Edit, Skill, AskUserQuestion
---

# /deck-publish — put the deck on the site

The deck already lives in the site's `res/` folder (`decks_dir`), so publishing is a check and a card, not a copy. Committing and pushing the site stays with the author.

Parse `$ARGUMENTS`: `deck` (slug, path or empty for the current folder), `--event` (where it was presented), `--video` (a YouTube id, if there is a recording).

## 1. Check and cover

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/publish-prep.sh <deck>
```

It stops when the deck is not inside the site repo or fails the full Craft check; report what it printed and stop too. On success it renders `cover.jpg` from the first slide and prints `path=`, `cover=` and `closing=`.

- `closing=end` → the deck has no Harold yet: ask whether to publish anyway or run `/deck-harold` first.
- Look at `cover.jpg` before going on.

## 2. Card

Read the site's `CLAUDE.md` first: it fixes the domain, the language rules and what not to touch. Then add a card to the "Featured Presentations" section of `<site>/index.html`, after the last `video-card`, copying the structure of the newest deck card (`a.deck-cover` with the cover image, then a `video-info` block per language). Links are relative to the site: `<path>/index.html` and the `cover=` path. With `--video`, follow the site's video card pattern instead of the cover link.

Title and description in every site language. Write them with the `my-voice` skill: this is public text on the author's behalf. Two sentences: what the talk is about and what the listener takes away, plus the event if given. No invented facts — take them from the slides.

## 3. Report

Show `git -C <site> status --short` and the card diff, open `<site>/index.html` in the browser, and remind that the site goes live after the author commits and pushes.
