#!/usr/bin/env bash
# Puts a deck that lives outside the site repo into <site>/res/<slug>: the full
# Craft check, then Craft's release (only the files the deck links to, cache
# busters on CSS and scripts) synced over the old copy. --hidden, or a site copy
# that already had it, keeps <meta name="robots" content="noindex, nofollow">.
# Usage: publish-release.sh [deck] [--slug name] [--hidden]

source "$(dirname "$0")/lib.sh"

deck_arg="" slug="" hidden=0 prev=""
for arg in "$@"; do
  if [[ "$prev" == --slug ]]; then slug="$arg"
  elif [[ "$arg" == --hidden ]]; then hidden=1
  elif [[ "$arg" != --slug ]]; then deck_arg="$arg"; fi
  prev="$arg"
done

td_require "$deck_arg" || exit 1
site="$(td_site_repo)"
[[ -n "$site" && -d "$site" ]] || { echo "talk-deck: site_repo is not set or missing" >&2; exit 1; }
slug="${slug:-$(basename "$deck")}"
[[ "$slug" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "talk-deck: bad slug '$slug'" >&2; exit 1; }
target="$site/res/$slug"
# rsync --delete over the deck itself would wipe every file the release leaves out.
[[ "$(cd "$deck" && pwd -P)" != "$(cd "$target" 2>/dev/null && pwd -P)" ]] \
  || { echo "talk-deck: $deck is already the site copy; publish it without publish-release.sh" >&2; exit 1; }

python3 "$craft/scripts/check_project.py" "$deck" --full || { echo "talk-deck: the deck fails the full check" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
python3 "$craft/scripts/release.py" "$deck" --out "$work" --name "$slug" --check static >"$work/release.log" 2>&1 \
  || { cat "$work/release.log" >&2; echo "talk-deck: release.py failed" >&2; exit 1; }

[[ -f "$target/index.html" ]] && grep -q 'name="robots" content="noindex' "$target/index.html" && hidden=1
# noindex goes into the release before the sync, so a hidden deck is never live without it.
if (( hidden )); then
  python3 - "$work/$slug/index.html" <<'PY' || exit 1
import re, sys
path = sys.argv[1]
html = re.sub(r'\n?<meta name="robots"[^>]*>', "", open(path, encoding="utf-8").read())
m = re.search(r'<meta name="viewport"[^>]*>', html) or re.search(r"<head[^>]*>", html)
if not m:
    sys.exit("talk-deck: no <head> in index.html")
html = html[:m.end()] + '\n<meta name="robots" content="noindex, nofollow">' + html[m.end():]
open(path, "w", encoding="utf-8").write(html)
PY
fi
mkdir -p "$target"
# The site keeps its card cover next to the deck; the organizer README is for the archive only.
rsync -a --delete --exclude /cover.jpg --exclude /README.txt "$work/$slug/" "$target/" || exit 1

echo "deck=$target"
echo "path=res/$slug"
echo "hidden=$hidden"
