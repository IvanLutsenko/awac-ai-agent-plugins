#!/usr/bin/env bash
# Review materials for a deck roast, in a fresh temp folder.
# Usage: review-pack.sh [deck]
#   deck.pdf           one page per slide, final frames
#   final/NN-key.png   final frame of every slide
#   shots/dark-NNN.png every reveal step, from Craft's full check
#   slides.txt         "NN key: pages a-b" — slide to step pages
# The full Craft check runs on the way; a failing deck still gets a pack,
# the check's verdict is printed as check=ok|failed for the reviewers.

source "$(dirname "$0")/lib.sh"

td_require "${1:-}" || exit 1
pack="$(mktemp -d "${TMPDIR:-/tmp}/deck-review.XXXXXX")"

if python3 "$craft/scripts/check_project.py" "$deck" --full --shots "$pack/shots" > "$pack/check.log" 2>&1; then
  check=ok
else
  check=failed
fi
bash "$(dirname "$0")/frames.sh" "$deck" "$pack/final" >/dev/null || exit 1
td_print_final "$deck" "$pack/deck.pdf" || { echo "talk-deck: no PDF was written" >&2; exit 1; }
python3 "$craft/scripts/deck_map.py" "$deck" --json > "$pack/map.json" || exit 1
python3 - "$pack/map.json" > "$pack/slides.txt" <<'PY' || exit 1
import json, sys
pages = json.load(open(sys.argv[1]))
order, spans = [], {}
for entry in pages:
    key = entry["key"]
    if key not in spans:
        order.append(key)
        spans[key] = [entry["page"], entry["page"]]
    spans[key][1] = entry["page"]
for n, key in enumerate(order, 1):
    first, last = spans[key]
    print(f"{n:02d} {key}: pages {first}-{last}")
PY

echo "pack=$pack"
echo "deck=$deck"
echo "slides=$(wc -l < "$pack/slides.txt" | tr -d ' ')"
echo "pages=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$pack/map.json")"
echo "check=$check"
echo "shots=$(ls "$pack/shots" 2>/dev/null | wc -l | tr -d ' ')"
[[ "$check" == ok ]] || echo "talk-deck: the full check failed, see $pack/check.log; shots/ may be incomplete" >&2
