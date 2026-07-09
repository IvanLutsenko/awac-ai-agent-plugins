#!/bin/bash

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // "."' 2>/dev/null)
[ -z "$CWD" ] && CWD="."

# 1. Check user-configured custom message
CONFIG="$CWD/.claude/locale-notifications.local.md"
if [ -f "$CONFIG" ]; then
    custom=$(python3 -c "
import re, sys
text = open(sys.argv[1]).read()
m = re.search(r'^message:\s*(.+)$', text, re.MULTILINE)
if m:
    value = m.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('\"', \"'\"):
        value = value[1:-1]
    print(value)
" "$CONFIG" 2>/dev/null)
    [ -n "$custom" ] && msg="$custom"
fi

# 2. Auto-translate if no custom message
if [ -z "$msg" ]; then
    locale=$(defaults read -g AppleLocale 2>/dev/null || echo 'en_US')
    lang=${locale:0:2}

    if [ "$lang" = "en" ]; then
        msg="Claude needs attention"
    else
        # Check cache
        CACHE_DIR="$HOME/.cache/locale-notifications"
        CACHE_FILE="$CACHE_DIR/${lang}.txt"

        if [ -f "$CACHE_FILE" ]; then
            msg=$(cat "$CACHE_FILE")
        else
            # Translate via Google Translate API (one-time, cached)
            msg=$(curl -s --max-time 3 \
                "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=${lang}&dt=t&q=Claude+needs+attention" \
                2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)[0][0][0])" 2>/dev/null)

            # Cache successful translation
            if [ -n "$msg" ]; then
                mkdir -p "$CACHE_DIR"
                echo "$msg" > "$CACHE_FILE"
            fi
        fi

        # Fallback to English
        [ -z "$msg" ] && msg="Claude needs attention"
    fi
fi

osascript -e 'on run argv' \
    -e 'display notification (item 1 of argv) with title "Claude Code"' \
    -e 'end run' -- "$msg"
