#!/bin/bash
# Start tracking for a project
# Usage: start-tracking.sh <project-name> [goal] [actions...]
#
# Creates .claude/obsidian-tracking.json with ISO timestamp

PROJECT="${1:?Usage: start-tracking.sh <project-name> [goal] [actions...]}"
GOAL="${2:-}"

# Shift past project and goal (if present)
if [ $# -ge 2 ]; then
  shift 2
else
  shift $#
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p .claude
python3 - "$PROJECT" "$GOAL" "$TIMESTAMP" "$@" > .claude/obsidian-tracking.json <<'PY'
import json
import sys

project, goal, timestamp, *actions = sys.argv[1:]
json.dump(
    {
        "project": project,
        "goal": goal,
        "actions": actions,
        "startedAt": timestamp,
    },
    sys.stdout,
    ensure_ascii=False,
    indent=2,
)
sys.stdout.write("\n")
PY

echo "Tracking started: project=$PROJECT, goal=$GOAL, started=$TIMESTAMP"
