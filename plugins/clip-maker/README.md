# Clip Maker

Automated vertical clip creator for talks and presentations. Combines Whisper transcription + Claude analysis (moment finding + smart crop) + ffmpeg processing.

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install clip-maker
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add clip-maker@awac-ai-agent-plugins
```

Dependencies (auto-installed on first run):
- `ffmpeg` (via brew)
- `openai-whisper` (via `uv pip`, fallback: `pip3`)

## Quick Start

```bash
/clip-maker ~/Downloads/my-talk.mp4                     # Full pipeline
/clip-maker ~/Downloads/my-talk.mp4 --auto              # Skip manual selection
/clip-maker ~/Downloads/my-talk.mp4 --no-subtitles      # Without subtitles
/clip-maker ~/Downloads/my-talk.mp4 --api               # Use OpenAI Whisper API
/transcribe ~/Downloads/my-talk.mp4                      # Only transcribe
/find-moments ~/Downloads/transcript.json                # Only find moments
```

## Status

**Version:** 1.3.1 | **Status:** Beta

**What's New in 1.3.1:**
- Fixed Claude agent names so `/clip-maker` resolves the expected agent types
- Fixed quoting and path handling in `transcribe.sh`, `cut-clip.sh`, and `extract-frames.sh`
- Added explicit error reporting for Whisper API / ffmpeg failures and subtitle input guards
- Switched Python dependency installs to `uv` first and removed silent Pillow auto-install from subtitle burn

**What's New in 1.3.0:**
- YouTube URL support via yt-dlp (pass URL instead of file path)
- Auto-download best quality up to 1080p

**What's New in 1.2.0:**
- Subtitles via Pillow direct frame rendering (precise positioning, Cyrillic support)
- Baskerville 60px font with word wrap and black outline
- `--prompt` option for whisper initial_prompt (dramatically improves domain term recognition)
- Dropped moviepy dependency (only Pillow needed)

**What's New in 1.1.0:**
- Subtitles via moviepy + Pillow (no libass/freetype dependency)

## Commands

### `/clip-maker <video> [options]`

Full pipeline: video → transcribe → find moments → crop → cut → subtitles → copy.

**Options:**
- `--duration N` — target clip duration in seconds (default: 60)
- `--auto` — skip manual moment selection
- `--no-subtitles` — don't burn subtitles
- `--no-copy` — skip social media copy generation
- `--api` — use OpenAI Whisper API (requires `OPENAI_API_KEY`)
- `--language LANG` — transcription language (default: ru)

**Output:** `{video_name}_clips/` directory with:
- `clip_01.mp4`, `clip_02.mp4`, ... — vertical 1080x1920 clips
- `copy.md` — social media descriptions (YouTube Shorts, Reels, TikTok)
- `manifest.json` — metadata for all clips
- `transcript.json` — full transcript (for reference)
- `moments.json` — selected moments (for reference)

### `/transcribe <video> [--api] [--language ru]`

Transcribe a video file. Outputs JSON with timestamped segments.

### `/find-moments <transcript_or_video> [--duration 60]`

Find interesting moments in a transcript or video.

## Pipeline

```
1. install-deps.sh     → check/install ffmpeg + whisper
2. transcribe.sh       → video → transcript.json
3. moment-finder agent → transcript → moments (opus)
   ↓ (manual selection unless --auto)
4. extract-frames.sh   → moments → PNG frames
5. crop-analyzer agent → frames → crop coordinates (sonnet + vision)
6. cut-clip.sh         → video + crop → vertical clips
7. burn-subtitles.sh   → clips + transcript → clips with subtitles
8. copywriter agent    → moments → social media copy (sonnet)
```

## Architecture

- **Scripts** (fast, deterministic): ffmpeg/whisper operations
- **Agents** (LLM, where intelligence needed):
  - `moment-finder` (opus) — finds engaging moments from transcript
  - `crop-analyzer` (sonnet) — determines speaker position from frames
  - `copywriter` (sonnet) — generates platform-specific descriptions

## Author

Ivan Lutsenko — [@IvanLutsenko](https://github.com/IvanLutsenko)

## License

MIT
