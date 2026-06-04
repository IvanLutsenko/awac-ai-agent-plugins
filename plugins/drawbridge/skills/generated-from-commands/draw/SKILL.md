---
name: drawbridge-draw
description: Crafts a target-tuned image-gen prompt from a short brief, copies it to clipboard, opens the target web UI. Use when the user invokes /draw.
version: 0.1.0
---

> Converted from Claude Code command `/draw`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# /draw — bridge brief to image-gen web UI

## Arguments

Parse `$ARGUMENTS`:
- `-t <target>` — optional target override. One of `gemini`, `chatgpt`, `grok`, `midjourney`.
- Everything else (joined) — the brief.

If no brief is given, stop and report: `Usage: /draw [-t target] <brief>`.

## Steps

### 1. Resolve target and translate flag

```bash
source plugins/drawbridge/scripts/lib.sh
echo "default_target=$(db_default_target)"
echo "translate=$(db_translate_enabled)"
```

If user passed `-t`, use that value. Otherwise use `db_default_target`. Validate against the allowed set; if invalid, stop and report.

### 2. Craft the prompt

Invoke the `prompt-crafting` skill (it ships with this plugin). Pass the brief, the target, and the translate flag. The skill returns ONLY the final prompt — no labels, no quoting.

If translate flag is `true` and the brief is non-English, the skill produces an English prompt.

### 3. Copy to clipboard + log + open

```bash
PROMPT=$(cat <<'PROMPT_EOF'
<final prompt here>
PROMPT_EOF
)
TARGET="<resolved target>"
BRIEF="<original brief>"

source plugins/drawbridge/scripts/lib.sh
printf "%s" "$PROMPT" | db_copy_clipboard
db_history_append "$TARGET" "$BRIEF" "$PROMPT"
db_open_url "$(db_target_url "$TARGET")"
```

### 4. Report to the user

Format:

```
target: <target>
prompt copied to clipboard, opening <url>

next: Cmd+V in the page, generate, copy the image, paste where you need it.
```

Show the prompt itself in a fenced block beneath, so the user can audit / copy manually if pbcopy fails.
