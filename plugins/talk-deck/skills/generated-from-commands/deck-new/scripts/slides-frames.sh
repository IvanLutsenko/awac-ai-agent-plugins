#!/usr/bin/env bash
# Frames for /deck-google-slides: 2x PNGs, GIFs of counting steps and frames.json.
# Usage: slides-frames.sh [deck] <outdir> [--steps] [--only key,key]

source "$(dirname "$0")/lib.sh"

deck_arg="" out="" rest=()
for arg in "$@"; do
  if [[ "$arg" == --* || "${prev:-}" == --only ]]; then rest+=("$arg")
  elif [[ -z "$out" ]]; then out="$arg"
  else deck_arg="$out"; out="$arg"; fi
  prev="$arg"
done
[[ -n "$out" ]] || { echo "usage: slides-frames.sh [deck] <outdir> [--steps] [--only key,key]" >&2; exit 1; }
td_require "$deck_arg" || exit 1
[[ " ${rest[*]:-} " == *" --steps "* ]] && { command -v ffmpeg >/dev/null || { echo "talk-deck: ffmpeg not found (brew install ffmpeg)" >&2; exit 1; }; }
# ${rest[@]+...}: bash 3.2 under set -u treats an empty array as unbound.
CRAFT_HOME="$craft" node "$(dirname "$0")/slides-frames.mjs" "$deck" "$out" ${rest[@]+"${rest[@]}"}
