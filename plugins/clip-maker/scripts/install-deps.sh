#!/bin/bash
# install-deps.sh — check and install ffmpeg + whisper
# Usage: install-deps.sh [--api]

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_api=false
for arg in "$@"; do
  [[ "$arg" == "--api" ]] && check_api=true
done

errors=0

# ffmpeg
if command -v ffmpeg &>/dev/null; then
  echo -e "${GREEN}✓${NC} ffmpeg found: $(ffmpeg -version 2>&1 | head -1)"
else
  echo -e "${YELLOW}⟳${NC} Installing ffmpeg..."
  if command -v brew &>/dev/null; then
    brew install ffmpeg
  else
    echo -e "${RED}✗${NC} brew not found. Install ffmpeg manually: https://ffmpeg.org/download.html"
    errors=$((errors + 1))
  fi
fi

# whisper (local mode)
if ! $check_api; then
  if command -v whisper &>/dev/null; then
    echo -e "${GREEN}✓${NC} whisper CLI found"
  elif python3 -c "import whisper" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} whisper Python module found"
  else
    echo -e "${YELLOW}⟳${NC} Installing openai-whisper..."
    if command -v uv &>/dev/null; then
      uv pip install openai-whisper
    elif command -v pip3 &>/dev/null; then
      pip3 install openai-whisper
    else
      echo -e "${RED}✗${NC} uv/pip3 not found. Install whisper manually: uv pip install openai-whisper"
      errors=$((errors + 1))
    fi
  fi
fi

# yt-dlp (for YouTube downloads)
if command -v yt-dlp &>/dev/null; then
  echo -e "${GREEN}✓${NC} yt-dlp found"
else
  echo -e "${YELLOW}⟳${NC} Installing yt-dlp..."
  if command -v brew &>/dev/null; then
    brew install yt-dlp
  elif command -v uv &>/dev/null; then
    uv pip install yt-dlp
  elif command -v pip3 &>/dev/null; then
    pip3 install yt-dlp
  else
    echo -e "${RED}✗${NC} yt-dlp not found. Install: brew install yt-dlp"
    errors=$((errors + 1))
  fi
fi

# Pillow (for subtitle rendering)
if python3 -c "from PIL import ImageFont" 2>/dev/null; then
  echo -e "${GREEN}✓${NC} Pillow found"
else
  echo -e "${YELLOW}⟳${NC} Installing Pillow..."
  if command -v uv &>/dev/null; then
    uv pip install Pillow || {
      echo -e "${RED}✗${NC} Failed to install Pillow. Install manually: uv pip install Pillow"
      errors=$((errors + 1))
    }
  elif command -v pip3 &>/dev/null; then
    pip3 install Pillow || {
      echo -e "${RED}✗${NC} Failed to install Pillow. Install manually: pip3 install Pillow"
      errors=$((errors + 1))
    }
  else
    echo -e "${RED}✗${NC} uv/pip3 not found. Install Pillow manually: uv pip install Pillow"
    errors=$((errors + 1))
  fi
fi

# API mode — check OPENAI_API_KEY
if $check_api; then
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    echo -e "${GREEN}✓${NC} OPENAI_API_KEY is set"
  else
    echo -e "${RED}✗${NC} OPENAI_API_KEY not set. Export it: export OPENAI_API_KEY=sk-..."
    errors=$((errors + 1))
  fi
fi

if [[ $errors -gt 0 ]]; then
  echo -e "\n${RED}$errors dependency issue(s) found. Fix them before proceeding.${NC}"
  exit 1
fi

echo -e "\n${GREEN}All dependencies OK.${NC}"
