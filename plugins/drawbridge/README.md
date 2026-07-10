# drawbridge

Bridge between a short brief and image-gen web UIs (Gemini Imagen 3, ChatGPT DALL-E 3, Grok Aurora, Midjourney). No API keys, no payments — uses your existing browser sessions.

Version: 0.1.1

## What's New in 0.1.1

- Fixed `drawbridge.local.md` frontmatter parsing so a markdown `---` in the body cannot reopen config parsing and override settings.

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install drawbridge
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add drawbridge@awac-ai-agent-plugins
```

## Flow

```
/draw закат на байкале с медведем у воды
   │
   ├─ pick target from settings (or -t flag)
   ├─ craft target-tuned prompt (translated to English by default)
   ├─ copy prompt to clipboard
   └─ open target's web UI

→ Cmd+V in the page → generate → copy image → paste where you need it
```

## Commands

- `/draw <brief>` — main. Crafts prompt, copies to clipboard, opens target UI.
- `/draw -t <target> <brief>` — override target for one call.
- `/redraw [-t target]` — variation of the last brief; same or different target.
- `/draw-prompt <brief>` — same as `/draw` but does NOT open the browser.
- `/draw-config [show | set <key> <value>]` — view or change defaults.

Targets: `gemini`, `chatgpt`, `grok`, `midjourney`.

## Settings

User-global: `~/.claude/drawbridge.local.md`. Project-local override: `<project>/.claude/drawbridge.local.md`.

```yaml
---
default_target: gemini          # gemini | chatgpt | grok | midjourney
translate_to_english: true
---
```

Use `/draw-config set default_target chatgpt` to change without editing the file.

## Per-target prompt tuning

The `prompt-crafting` skill knows the format each generator likes:

- **Gemini (Imagen 3)** — flowing prose, ~480 tokens, photoreal sweet spot, inline negatives.
- **ChatGPT (DALL-E 3)** — concise structured natural language; GPT-4 rewrites internally.
- **Grok (Aurora)** — dense descriptive prose, looser content rules, photoreal with people.
- **Midjourney** — comma-separated tags + `--ar`, `--v`, `--style`, `--no` suffixes.

Style is decided **by context** of the brief, not from fixed presets — photoreal for scenes, illustration for concepts, respect explicit medium hints ("в стиле акварели", "лого", "пиксель-арт").

## History

Last 200 prompts kept in `~/.claude/plugins/drawbridge/history.jsonl`. `/redraw` reads the most recent entry.

## Limits

- macOS only (`pbcopy`, `open`). Linux/Windows support is a follow-up.
- You must be logged into the target service in your browser.
- Imagen via the web has stricter content rules than via API; use Grok if blocked.
