#!/usr/bin/env bash
# Attaches the rehearsal timer to a deck: copies rehearsal.js next to deck.js,
# adds its <script> before </body> and sets the talk length. Idempotent;
# a later run refreshes the script and, with minutes, the length.
# Usage: rehearse.sh [deck] [minutes]

source "$(dirname "$0")/lib.sh"

# A number is the length unless it names a deck folder.
deck_arg="" minutes=""
for arg in "$@"; do
  if [[ "$arg" =~ ^[0-9]+$ ]] && ! td_resolve_deck "$arg" >/dev/null 2>&1; then minutes="$arg"; else deck_arg="$arg"; fi
done
deck="$(td_resolve_deck "$deck_arg")" || { echo "talk-deck: no Craft deck at '${deck_arg:-$PWD}'" >&2; exit 1; }
index="$deck/index.html"

python3 - "$index" "$minutes" <<'PY' || exit 1
import re, sys
path, minutes = sys.argv[1], sys.argv[2]
html = open(path, encoding="utf-8").read()
deck = re.search(r'<div class="deck"[^>]*>', html)
if not deck:
    sys.exit('talk-deck: no <div class="deck"> in index.html')
if 'src="rehearsal.js"' not in html:
    # After every other script: the timer needs window.craftDeck and the panel.
    i = html.rfind("</body>")
    if i < 0:
        sys.exit("talk-deck: no </body> in index.html")
    html = html[:i] + '<script src="rehearsal.js"></script>\n' + html[i:]
tag = deck.group(0)
if minutes:
    tag = re.sub(r' data-talk-minutes="\d+"', "", tag)
if "data-talk-minutes" not in tag:
    tag = tag.replace('<div class="deck"', f'<div class="deck" data-talk-minutes="{minutes or 20}"', 1)
html = html.replace(deck.group(0), tag, 1)
open(path, "w", encoding="utf-8").write(html)
print("minutes=" + re.search(r'data-talk-minutes="(\d+)"', tag).group(1))
PY
cp "$(dirname "$0")/rehearsal.js" "$deck/rehearsal.js" || exit 1
echo "deck=$deck"
