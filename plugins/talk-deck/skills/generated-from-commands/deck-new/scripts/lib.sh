#!/usr/bin/env bash
# talk-deck — shared bash utilities for commands and the hook.
# Intended to be `source`d. Settings live in YAML frontmatter of
# ~/.claude/talk-deck.local.md (project-local override: .claude/talk-deck.local.md).

set -uo pipefail

td_config_path() {
  local project_cfg=".claude/talk-deck.local.md"
  local user_cfg="${HOME}/.claude/talk-deck.local.md"
  if [[ -f "$project_cfg" ]]; then
    echo "$project_cfg"
  elif [[ -f "$user_cfg" ]]; then
    echo "$user_cfg"
  fi
}

# Read a key from the config frontmatter. Stdout: value or empty.
td_get() {
  local file
  file="$(td_config_path)"
  [[ -z "$file" ]] && return 0
  awk -v k="$1" '
    /^---[[:space:]]*$/ { state++; if (state > 1) exit; next }
    state == 1 {
      idx = index($0, ":")
      if (idx == 0) next
      name = substr($0, 1, idx - 1); sub(/[[:space:]]+$/, "", name)
      val = substr($0, idx + 1); sub(/^[[:space:]]+/, "", val); sub(/[[:space:]]+$/, "", val)
      gsub(/^["'\'']|["'\'']$/, "", val)
      if (name == k) { print val; exit }
    }
  ' "$file"
}

td_expand() { local v="$1"; echo "${v/#\~/$HOME}"; }

td_author()   { td_get author; }
td_contact()  { td_get contact; }
td_lang()     { local v; v="$(td_get lang)"; echo "${v:-ru}"; }
td_site_repo() { local v; v="$(td_get site_repo)"; [[ -n "$v" ]] && td_expand "$v"; }

# Where decks live: decks_dir, else <site_repo>/res.
td_decks_dir() {
  local v
  v="$(td_get decks_dir)"
  if [[ -n "$v" ]]; then td_expand "$v"; return; fi
  v="$(td_site_repo)"
  [[ -n "$v" ]] && echo "$v/res"
}

# Craft skill root: config, $CRAFT_HOME, then the usual skill folders.
# A configured craft_home that is not a Craft skill is an error, not a fallback.
td_craft_home() {
  local configured
  configured="$(td_get craft_home)"
  if [[ -n "$configured" ]]; then
    configured="$(td_expand "$configured")"
    [[ -f "$configured/scripts/scaffold.py" ]] && { echo "$configured"; return; }
    echo "talk-deck: craft_home $configured is not a Craft skill" >&2
    return 1
  fi
  local candidates=("${CRAFT_HOME:-}" \
    "$HOME/.claude/skills/craft" "$HOME/.agents/skills/craft" "$HOME/.codex/skills/craft" "$HOME/projects/craft")
  local c
  for c in "${candidates[@]}"; do
    [[ -n "$c" && -f "$c/scripts/scaffold.py" ]] && { echo "$c"; return; }
  done
  return 1
}

# Craft's checks need a Chromium; on macOS fall back to Google Chrome.
td_chromium() {
  if [[ -n "${CHROMIUM:-}" ]]; then echo "$CHROMIUM"; return; fi
  local mac="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  if [[ -x "$mac" ]]; then echo "$mac"; return; fi
  local name
  for name in chromium chromium-browser google-chrome; do
    command -v "$name" >/dev/null && { command -v "$name"; return; }
  done
}

# A Craft deck folder: has index.html and deck-theme.css.
td_is_deck() { [[ -f "$1/index.html" && -f "$1/deck-theme.css" ]]; }

# Walk up from a path to the deck folder that contains it. Fails when there is none.
td_deck_of() {
  local dir="$1"
  [[ -f "$dir" ]] && dir="$(dirname "$dir")"
  while [[ -n "$dir" && "$dir" != "/" && "$dir" != "." ]]; do
    if td_is_deck "$dir"; then echo "$dir"; return 0; fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# Resolve a deck from a slug, a path or the current folder. Fails when it is not a deck.
td_resolve_deck() {
  local arg="${1:-}" decks
  if [[ -n "$arg" ]]; then
    if [[ -d "$arg" ]] && td_deck_of "$(cd "$arg" && pwd)"; then return; fi
    decks="$(td_decks_dir)"
    if [[ -n "$decks" && -d "$decks/$arg" ]]; then td_deck_of "$decks/$arg"; return; fi
    return 1
  fi
  td_deck_of "$PWD"
}

# Shared start of every script: the deck, Craft and a Chromium, or a clear failure.
td_require() {
  deck="$(td_resolve_deck "${1:-}")" || { echo "talk-deck: no Craft deck at '${1:-$PWD}'" >&2; return 1; }
  craft="$(td_craft_home)" || { echo "talk-deck: the Craft skill is not installed" >&2; return 1; }
  CHROMIUM="$(td_chromium)"
  [[ -n "$CHROMIUM" ]] || { echo "talk-deck: no Chromium; set CHROMIUM" >&2; return 1; }
  export CHROMIUM
}
