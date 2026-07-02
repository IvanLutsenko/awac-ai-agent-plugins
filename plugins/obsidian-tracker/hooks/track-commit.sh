#!/bin/bash
# PostToolUse:Bash — capture git commit hashes to tracking
# Only activates for git commit commands, ignores everything else

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')

TRACKING_FILE="${CWD}/.claude/obsidian-tracking.json"

# No tracking → skip
if [ ! -f "$TRACKING_FILE" ]; then
  echo '{}'
  exit 0
fi

# Check if the bash command was a git commit.
# Matches "git commit" with optional flags between git and commit, anywhere in
# a compound command: "cd x && git commit", "git -C path commit", "git -c k=v commit".
# Word-boundary anchors avoid false positives like "git log | grep commit".
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
if ! echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])git([[:space:]]+-[cC][[:space:]]*[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)'; then
  echo '{}'
  exit 0
fi

# Extract commit hash from output (short hash from "1234567 commit message" or "[branch 1234567]")
OUTPUT=$(echo "$INPUT" | jq -r '.tool_output.stdout // .tool_output // ""' 2>/dev/null)
HASH=$(echo "$OUTPUT" | grep -oE '\b[a-f0-9]{7,40}\b' | head -1)

if [ -z "$HASH" ]; then
  echo '{}'
  exit 0
fi

SHORT_HASH="${HASH:0:7}"

# Add commit to tracking
jq --arg h "$SHORT_HASH" --arg a "💾 commit $SHORT_HASH" '
  .linkedCommits = ((.linkedCommits // []) + [$h] | unique) |
  .actions += [$a]
' "$TRACKING_FILE" > "${TRACKING_FILE}.tmp" 2>/dev/null \
  && mv "${TRACKING_FILE}.tmp" "$TRACKING_FILE" 2>/dev/null

echo '{}'
