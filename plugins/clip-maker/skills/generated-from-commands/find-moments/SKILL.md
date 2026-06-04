---
name: clip-maker-find-moments
description: Find interesting moments in a transcript or video. Use when the user invokes /find-moments.
version: 0.1.0
---

> Converted from Claude Code command `/find-moments`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Find Interesting Moments

Analyze a transcript (or video) to find the most engaging moments for vertical clips.

## Arguments

Parse `$ARGUMENTS` for:
- `<path>` — **required**, path to either:
  - `transcript.json` — pre-existing transcript
  - video file (`.mp4`, `.mov`, `.avi`, etc.) — will transcribe first
- `--duration N` — target moment duration in seconds (default: 60)

## Steps

### 1. Determine input type

Check the file extension:
- If `.json` → use as transcript directly
- If video file → transcribe first using:
  ```bash
  bash plugins/clip-maker/scripts/install-deps.sh
  bash plugins/clip-maker/scripts/transcribe.sh "<video_path>" "<output_dir>"
  ```

### 2. Find moments

Launch the `moment-finder` agent:

```
Agent(subagent_type="clip-maker:moment-finder", model="opus", prompt="
Analyze the transcript and find the most engaging moments.

- Transcript path: <transcript_path>
- Target duration: <duration> seconds
- Output path: <output_dir>/moments.json

Read the transcript, find the best moments, and write moments.json.
")
```

### 3. Display results

Read `moments.json` and present moments to the user as a formatted list:
- Number, title, time range (MM:SS - MM:SS), score
- The key quote from each moment
