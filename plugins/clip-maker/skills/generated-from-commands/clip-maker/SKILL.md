---
name: clip-maker-clip-maker
description: Create vertical clips from a video. Full pipeline: transcribe → find moments → crop → cut → subtitles → copy. Use when the user invokes /clip-maker.
version: 0.1.0
---

> Converted from Claude Code command `/clip-maker`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Clip Maker — Full Pipeline

Create vertical (9:16) clips from a horizontal video, optimized for Reels/Shorts/TikTok.

## Arguments

Parse `$ARGUMENTS` for:
- `<video_path_or_url>` — **required**, path to source video OR YouTube/web URL
- `--duration N` — target clip duration in seconds (default: 60)
- `--auto` — skip manual moment selection, use all found moments
- `--no-subtitles` — don't burn subtitles into clips
- `--api` — use OpenAI Whisper API instead of local whisper
- `--no-copy` — skip social media copy generation
- `--language LANG` — transcription language (default: ru)
- `--prompt "terms"` — domain-specific terms for whisper (improves recognition of jargon, names, abbreviations)

## Pipeline

Execute steps sequentially. Report progress to the user after each step.

### Step 1: Check dependencies

```bash
bash plugins/clip-maker/scripts/install-deps.sh [--api if user passed --api]
```

If it fails, stop and report what's missing.

### Step 2: Download if URL

If `<video_path>` looks like a URL (starts with `http://`, `https://`, or `youtube.com`, `youtu.be`):

```bash
VIDEO_PATH=$(bash plugins/clip-maker/scripts/download-video.sh "<url>" ~/Downloads)
```

The script outputs the downloaded file path. Use it as `<video_path>` for subsequent steps.

### Step 3: Setup output directory

Create output directory next to the video: `{video_dir}/{video_name}_clips/`

### Step 4: Transcribe

```bash
bash plugins/clip-maker/scripts/transcribe.sh "<video_path>" "<output_dir>" [--api] [--language LANG] [--prompt "terms"]
```

This produces `<output_dir>/transcript.json`.

### Step 5: Find interesting moments

Launch the `moment-finder` agent:

```
Agent(subagent_type="clip-maker:moment-finder", model="opus", prompt="
Analyze the transcript and find the most engaging moments for vertical clips.

- Transcript path: <output_dir>/transcript.json
- Target clip duration: <duration> seconds
- Output path: <output_dir>/moments.json

Read the transcript, find the best moments, and write moments.json.
")
```

### Step 6: User selects moments (unless --auto)

If `--auto` is NOT set:
1. Read `moments.json`
2. Present the moments to the user as a numbered list showing: title, time range, quote, score
3. Ask which moments to keep (user can type numbers like "1,3,5" or "all")
4. Update `moments.json` to only include selected moments

If `--auto` IS set: proceed with all moments.

### Step 7: Extract frames

```bash
bash plugins/clip-maker/scripts/extract-frames.sh "<video_path>" "<output_dir>/moments.json" "<output_dir>"
```

### Step 8: Analyze crop positions

Launch the `crop-analyzer` agent:

```
Agent(subagent_type="clip-maker:crop-analyzer", model="sonnet", prompt="
Analyze frames to determine optimal crop positions for vertical clips.

- Frames directory: <output_dir>/frames/
- Source video dimensions: [get from ffprobe]
- Output path: <output_dir>/crop_coords.json

Read each moment's frames, locate the speaker, and write crop_coords.json.
")
```

### Step 9: Cut clips

```bash
bash plugins/clip-maker/scripts/cut-clip.sh "<video_path>" "<output_dir>/moments.json" "<output_dir>/crop_coords.json" "<output_dir>"
```

### Step 10: Burn subtitles (unless --no-subtitles)

```bash
bash plugins/clip-maker/scripts/burn-subtitles.sh "<output_dir>/moments.json" "<output_dir>/transcript.json" "<output_dir>"
```

### Step 11: Generate social media copy (unless --no-copy)

Launch the `copywriter` agent:

```
Agent(subagent_type="clip-maker:copywriter", model="sonnet", prompt="
Generate social media descriptions for the clips.

- Moments: <output_dir>/moments.json
- Output: <output_dir>/copy.md

Read moments.json and write copy.md with platform-specific descriptions.
")
```

### Step 12: Generate manifest and report

Create `<output_dir>/manifest.json` with metadata for all clips:
```json
{
  "source": "<video_path>",
  "created": "<timestamp>",
  "clips": [
    {
      "file": "clip_01.mp4",
      "title": "...",
      "start": 125.4,
      "end": 183.2,
      "duration": 57.8,
      "has_subtitles": true
    }
  ]
}
```

Report final summary:
- Number of clips created
- Output directory path
- Total duration of clips
- Whether copy.md was generated

### Cleanup

Remove intermediate files:
- `<output_dir>/frames/` directory
- `<output_dir>/transcript.json` — keep (useful reference)
- `<output_dir>/moments.json` — keep (useful reference)
- `<output_dir>/crop_coords.json` — remove
