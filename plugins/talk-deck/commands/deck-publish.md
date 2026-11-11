---
description: Publish a talk deck on the author's site — full Craft check, cover image, a presentation card in every site language, or a hidden page with no card. No commit or push.
argument-hint: "[deck] [--event name] [--video youtube-id] [--hidden | --public] [--slug name]"
allowed-tools: Bash(bash:*), Bash(git -C:*), Bash(open:*), Read, Edit, Skill, AskUserQuestion
---

# /deck-publish — put the deck on the site

A deck made in the site's `res/` folder (`decks_dir`) is already in place, so publishing is a check and a card. A deck kept elsewhere is first released into `<site>/res/<slug>`. Committing and pushing the site stays with the author.

Parse `$ARGUMENTS`: `deck` (slug, path or empty for the current folder), `--event` (where it was presented), `--video` (a YouTube id, if there is a recording), `--hidden` (reachable by its link only: `noindex`, no card), `--public` (a deck published hidden before now goes on the site: `noindex` off, card on), `--slug` (the folder name on the site for a deck kept elsewhere; default: the deck folder's name).

## 0. A deck outside the site repo

When the deck is not inside `site_repo` (or for any `--hidden` publish of such a deck):

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/publish-release.sh <deck> [--slug name] [--hidden | --public]
```

It runs the full check, builds Craft's release (only linked files, cache busters on CSS and scripts) and syncs it over `<site>/res/<slug>`, keeping the card's `cover.jpg`. A site copy that already had `noindex` keeps it, so a hidden deck stays hidden on every re-publish; `--public` drops it. It prints `deck=` (the site copy), `path=` and `hidden=`. With `hidden=1` skip the card: report the page URL on the site's domain (from the site's `CLAUDE.md`) and go to step 3. Otherwise continue with step 1 on the site copy.

`--public` for a deck already inside the site repo: remove its robots meta and go on with step 1.

`--hidden` for a deck already inside the site repo: add `<meta name="robots" content="noindex, nofollow">` after the viewport meta of its `index.html` (replace any other robots meta), run the full check, skip the card and go to step 3.

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

Show `git -C <site> status --short` and the card diff, open `<site>/index.html` in the browser, and remind that the site goes live after the author commits and pushes. The site repo may get commits of its own (for example a plugin version sync), so the push may need `git pull --rebase` first.
