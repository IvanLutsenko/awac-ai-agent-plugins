#!/usr/bin/env bash
# drawbridge — shared bash utilities for commands
# All functions are pure bash, no extra deps. Intended to be `source`d by command bash blocks.

set -uo pipefail

# Resolve XDG-style state dir for drawbridge (history etc.)
DRAWBRIDGE_STATE_DIR="${HOME}/.claude/plugins/drawbridge"
DRAWBRIDGE_HISTORY_FILE="${DRAWBRIDGE_STATE_DIR}/history.jsonl"

# Locate config file. Project-local first, then user-global.
db_config_path() {
  local project_cfg=".claude/drawbridge.local.md"
  local user_cfg="${HOME}/.claude/drawbridge.local.md"
  if [[ -f "$project_cfg" ]]; then
    echo "$project_cfg"
  elif [[ -f "$user_cfg" ]]; then
    echo "$user_cfg"
  else
    echo ""
  fi
}

# Read a YAML frontmatter key from a config file. Stdout: value or empty.
# Usage: db_config_get <file> <key>
db_config_get() {
  local file="$1"
  local key="$2"
  [[ -z "$file" || ! -f "$file" ]] && return 0
  awk -v k="$key" '
    BEGIN { state = 0 }
    /^---[[:space:]]*$/ {
      if (state == 0) {
        state = 1
        next
      }
      if (state == 1) {
        exit
      }
    }
    state == 1 {
      line = $0
      idx = index(line, ":")
      if (idx > 0) {
        name = line
        sub(/[[:space:]]*:.*$/, "", name)
        val = substr(line, idx + 1)
        sub(/^[[:space:]]+/, "", val)
        sub(/[[:space:]]+$/, "", val)
        gsub(/^["'\'']|["'\'']$/, "", val)
        if (name == k) { print val; exit }
      }
    }
  ' "$file"
}

# Resolve effective default_target with fallback chain.
db_default_target() {
  local cfg
  cfg="$(db_config_path)"
  local val
  val="$(db_config_get "$cfg" default_target)"
  echo "${val:-gemini}"
}

# Effective translate flag (default: true).
db_translate_enabled() {
  local cfg
  cfg="$(db_config_path)"
  local val
  val="$(db_config_get "$cfg" translate_to_english)"
  case "${val:-true}" in
    true|TRUE|yes|1) echo "true" ;;
    *) echo "false" ;;
  esac
}

# Map target → web UI URL.
db_target_url() {
  case "$1" in
    gemini)     echo "https://gemini.google.com/app" ;;
    chatgpt)    echo "https://chatgpt.com" ;;
    grok)       echo "https://grok.com" ;;
    midjourney) echo "https://www.midjourney.com/imagine" ;;
    *) return 1 ;;
  esac
}

# Copy stdin to clipboard (macOS).
db_copy_clipboard() {
  pbcopy
}

# Open a URL in the default browser (macOS).
db_open_url() {
  open "$1"
}

# Append a history record. Args: target, brief, prompt
db_history_append() {
  mkdir -p "$DRAWBRIDGE_STATE_DIR"
  local ts target brief prompt
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  target="$1"
  brief="$2"
  prompt="$3"
  python3 -c '
import json, sys
ts, target, brief, prompt = sys.argv[1:5]
print(json.dumps({"ts": ts, "target": target, "brief": brief, "prompt": prompt}, ensure_ascii=False))
' "$ts" "$target" "$brief" "$prompt" >> "$DRAWBRIDGE_HISTORY_FILE"

  # Rotation: keep last 200 entries.
  if [[ -f "$DRAWBRIDGE_HISTORY_FILE" ]]; then
    local lines
    lines=$(wc -l < "$DRAWBRIDGE_HISTORY_FILE" | tr -d ' ')
    if (( lines > 200 )); then
      tail -n 200 "$DRAWBRIDGE_HISTORY_FILE" > "${DRAWBRIDGE_HISTORY_FILE}.tmp"
      mv "${DRAWBRIDGE_HISTORY_FILE}.tmp" "$DRAWBRIDGE_HISTORY_FILE"
    fi
  fi
}

# Read last history entry as JSON. Empty if no history.
db_history_last() {
  [[ -f "$DRAWBRIDGE_HISTORY_FILE" ]] || return 0
  tail -n 1 "$DRAWBRIDGE_HISTORY_FILE"
}
