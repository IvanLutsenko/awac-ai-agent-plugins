#!/bin/bash
# PreCompact — carry active tracking state through compaction.
#
# Stdout of a PreCompact hook is joined into `newCustomInstructions` and handed
# to the compaction summarizer (executePreCompactHooks). So the channel is plain
# text, NOT JSON: PreCompact is absent from the hookSpecificOutput union, and the
# output-mapping switch has no PreCompact case — additionalContext would be
# silently dropped, and a JSON blob would land in the summarizer verbatim.
#
# Nothing to say → print nothing and exit 0. Even `{}` would be picked up as a
# custom instruction.

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."')

TRACKING_FILE="${CWD}/.claude/obsidian-tracking.json"

# Missing or malformed → stay silent rather than emit half-read state
jq -e . "$TRACKING_FILE" >/dev/null 2>&1 || exit 0

PROJECT=$(jq -r '.project // "unknown"' "$TRACKING_FILE")
GOAL=$(jq -r '.goal // ""' "$TRACKING_FILE")
ACTIONS=$(jq -r '(.actions // []) | length' "$TRACKING_FILE")

echo "Preserve this line verbatim in the summary: OBSIDIAN TRACKING ACTIVE: Project=${PROJECT}, Goal=${GOAL}, Actions=${ACTIONS}"
