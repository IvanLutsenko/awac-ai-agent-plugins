#!/bin/bash
# download-video.sh — download video from YouTube (or other yt-dlp supported sites)
# Usage: download-video.sh <url> <output_dir>
# Outputs the downloaded file path to stdout (last line)

set -euo pipefail

URL="$1"
OUTPUT_DIR="$2"

mkdir -p "$OUTPUT_DIR"

echo "Downloading video from: $URL" >&2

yt-dlp \
  -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best" \
  --merge-output-format mp4 \
  -o "${OUTPUT_DIR}/%(title)s.%(ext)s" \
  --no-playlist \
  --print after_move:filepath \
  "$URL"
