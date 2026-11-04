#!/usr/bin/env bash
# One PNG per slide in its final frame: <outdir>/NN-<key>.png, 1920x1080.
# --steps: one PNG per reveal step instead, <outdir>/NNN-<key>-<step>.png.
# Usage: frames.sh [deck] <outdir> [--steps]
# The slides are printed to a PDF (full bleed, no stage margins or screen
# decor) and rasterized with pdftoppm; names come from Craft's deck_map.py.

source "$(dirname "$0")/lib.sh"

steps=0 args=()
for arg in "$@"; do
  [[ "$arg" == --steps ]] && steps=1 || args+=("$arg")
done
(( ${#args[@]} >= 1 )) || { echo "usage: frames.sh [deck] <outdir> [--steps]" >&2; exit 1; }
outdir="${args[${#args[@]}-1]}"
deck_arg=""
(( ${#args[@]} >= 2 )) && deck_arg="${args[0]}"

td_require "$deck_arg" || exit 1
command -v pdftoppm >/dev/null || { echo "talk-deck: pdftoppm not found (brew install poppler)" >&2; exit 1; }

mkdir -p "$outdir"
outdir="$(cd "$outdir" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if (( steps )); then map_args=(--json) reveal=steps; else map_args=(--final --json) reveal=final; fi
python3 "$craft/scripts/deck_map.py" "$deck" "${map_args[@]}" > "$work/map.json" || { echo "talk-deck: deck_map.py failed" >&2; exit 1; }
td_print_final "$deck" "$work/deck.pdf" "$reveal" || { echo "talk-deck: no PDF was written" >&2; exit 1; }
pdftoppm -q -png -scale-to-x 1920 -scale-to-y 1080 "$work/deck.pdf" "$work/page" || exit 1

python3 - "$work" "$outdir" "$steps" <<'PY' || exit 1
import json, re, shutil, sys
from pathlib import Path
work, out, steps = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] == "1"
pages = json.loads((work / "map.json").read_text())
# pdftoppm pads page numbers to the width of the page count: page-01.png, page-001.png.
shots = sorted(work.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)\.png$", p.name).group(1)))
if len(shots) != len(pages):
    sys.exit(f"talk-deck: the PDF has {len(shots)} pages, the deck map {len(pages)}")
for entry, shot in zip(pages, shots):
    key = re.sub(r"[^a-z0-9-]", "-", (entry.get("key") or "slide").lower())
    name = f"{entry['page']:03d}-{key}-{entry['step']}.png" if steps else f"{entry['page']:02d}-{key}.png"
    shutil.move(shot, out / name)
PY

echo "frames=$outdir"
echo "count=$(ls "$outdir"/[0-9]*-*.png | wc -l | tr -d ' ')"
