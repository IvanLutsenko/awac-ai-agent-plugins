#!/usr/bin/env bash
# PostToolUse hook: after an edit inside a Craft deck, run the static check
# (sources only, about a second). A failure goes back to the agent (exit 2).
# Files outside a deck are ignored.

source "$(dirname "$0")/lib.sh"

file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))')" || {
  echo "talk-deck: the hook could not read the tool input" >&2; exit 1; }
[[ -z "$file" ]] && exit 0
deck="$(td_deck_of "$file")" || exit 0
craft="$(td_craft_home)" || { echo "talk-deck: Craft is not installed, the deck at $deck is not checked" >&2; exit 1; }

if ! out="$(python3 "$craft/scripts/check_project.py" "$deck" --static-only 2>&1)"; then
  echo "talk-deck: the static Craft check failed for $deck" >&2
  echo "$out" | tail -15 >&2
  exit 2
fi
exit 0
