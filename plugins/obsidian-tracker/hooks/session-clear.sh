#!/bin/bash
# SessionStart:clear — mechanically save raw session to Obsidian vault,
# then leave a marker file for the prompt hook to enrich with a summary.
# Guarantees data is saved even if Claude ignores the prompt hook.

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')

TRACKING_FILE="${CWD}/.claude/obsidian-tracking.json"

if [ ! -f "$TRACKING_FILE" ]; then
  echo '{}'
  exit 0
fi

# --- Read tracking data ---
PROJECT=$(jq -r '.project // ""' "$TRACKING_FILE")
GOAL=$(jq -r '.goal // ""' "$TRACKING_FILE")
STARTED_AT=$(jq -r '.startedAt // ""' "$TRACKING_FILE")

if [ -z "$PROJECT" ]; then
  echo '{}'
  exit 0
fi

# --- Resolve vault path ---
CONFIG_FILE="$HOME/.config/obsidian-tracker/config.json"
VAULT=""
if [ -f "$CONFIG_FILE" ]; then
  VAULT=$(jq -r '.vaultPath // ""' "$CONFIG_FILE")
fi
if [ -z "$VAULT" ]; then
  VAULT="${OBSIDIAN_VAULT:-$HOME/Documents/ObsidianVault/Projects}"
fi
VAULT=$(echo "$VAULT" | sed "s|\\\$HOME|$HOME|g")

PROJECT_DIR="$VAULT/$PROJECT"
if [ ! -d "$PROJECT_DIR" ]; then
  # Project dir not found — leave tracking file for prompt hook fallback
  echo '{}'
  exit 0
fi

# --- Write raw session to vault ---
SESSIONS_DIR="$PROJECT_DIR/Sessions"
mkdir -p "$SESSIONS_DIR"

DATE=$(date -u +"%Y-%m-%d")
TIME=$(date -u +"%H:%M")
SESSION_FILE="$SESSIONS_DIR/Session - $DATE.md"

# Build actions list
ACTIONS=$(jq -r '.actions[]?' "$TRACKING_FILE" | sed 's/^/- /')
if [ -z "$ACTIONS" ]; then
  ACTIONS="- No actions recorded"
fi

# Calculate duration
DURATION="unknown"
if [ -n "$STARTED_AT" ]; then
  START_EPOCH=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$STARTED_AT" +%s 2>/dev/null || echo "")
  if [ -n "$START_EPOCH" ]; then
    NOW_EPOCH=$(date +%s)
    DURATION_MINS=$(( (NOW_EPOCH - START_EPOCH) / 60 ))
    if [ "$DURATION_MINS" -ge 60 ]; then
      DURATION="$((DURATION_MINS / 60))h $((DURATION_MINS % 60))m"
    else
      DURATION="${DURATION_MINS}m"
    fi
  fi
fi

# Append session entry.
# CONTRACT: must match mcp/helpers.ts renderSessionEntry() exactly —
# pinned by the vitest golden test and the bats "format contract" test.
cat >> "$SESSION_FILE" << ENTRY


## Session - ${TIME} UTC (${DURATION})

### Goal
${GOAL:-No goal specified}

### Actions
${ACTIONS}

### Results
(auto-saved)

### Next Time
TBD

---
ENTRY

# --- Move tracking file for enrichment ---
mv "$TRACKING_FILE" "${CWD}/.claude/obsidian-session-saved.json"

# Best-effort: ask Claude to add semantic summary. Raw session is already saved above.
jq -n '{
  "systemMessage": "Raw session saved to Obsidian. If .claude/obsidian-session-saved.json exists, call addSessionSummary MCP with completed items and next steps, then delete the file. Brief confirmation."
}'
