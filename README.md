# AWAC AI Agent Plugins

Custom AI agent plugins by Ivan Lutsenko

## Installation

### Claude Code

Add the marketplace once, then install plugins as needed:

```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install crashlytics        # then any plugin by name
```

Compatibility: the previous repository slug,
`awac-claude-code-plugins`, is kept as a supported fallback for existing
Claude Code marketplace installations.

### Codex CLI

Most plugins here are dual-target and ship a Codex build (`.codex-plugin/` +
`skills/`), registered in the Codex marketplace manifest at
`.agents/plugins/marketplace.json`. Add the marketplace, then install a plugin
from it by name:

```bash
# Add this repo as a Codex marketplace (Git source — or pass a local clone path)
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins

# Install a plugin: PLUGIN@MARKETPLACE
codex plugin add combined-review@awac-ai-agent-plugins

# Verify
codex plugin marketplace list      # marketplaces and their roots
codex plugin list                  # plugins and install status
```

The marketplace name is `awac-ai-agent-plugins` (the `name` field of
`.agents/plugins/marketplace.json`). Codex snapshots it under
`~/.codex/.tmp/marketplaces/awac-ai-agent-plugins/` and records the source in
`~/.codex/config.toml`. Claude Code commands become Codex skills under
`skills/generated-from-commands/`, and agents become skills under
`skills/generated-from-agents/`.

> Codex-only caveat: `locale-notifications` is Claude Code-only (excluded from
> the Codex target).

## Available Plugins

### Crashlytics

Multi-platform crash analysis for Android & iOS with git blame forensics, code-level fixes, and a deterministic quality gate.

📚 **[Full Documentation](plugins/crashlytics/README.md)**

**Installation:**
```bash
/plugin install crashlytics
/crashlytics:install-permissions   # one-time: add read-only git/MCP to allowlist
```

**Quick Start:**
```bash
/crash-report ca8f7f21e3...        # Unified (auto-detects platform from config)
/crash-report-android               # Explicit Android
/crash-report-ios                    # Explicit iOS
/crash-config                       # Configure plugin settings
/crashlytics:install-permissions    # Add read-only allowlist to settings.json
```

**Status:** ✅ Production Ready | **Version:** 4.4.4

**What's New in 4.4.4:**
- Firebase MCP launcher pinned to `firebase-tools@15` instead of `@latest`, so plugin startup no longer drifts on silent major updates and works better offline once cached.
- After updating, restart the Claude Code session once so the new `.mcp.json` command is picked up.

**Features:**
- 4-step multi-agent pipeline: classifier → fetcher → forensics → validate-report.py
- Git blame forensics with mandatory assignee identification, on `origin/<default_branch>`
- Code-level fixes (before/after) ready to copy-paste
- MCP-primary fetch (`crashlytics_get_issue` + `crashlytics_batch_get_events`), REST `v1alpha` fallback, Manual mode for offline use
- Multi-language reports (English headers + body in any language)
- Configurable per-project settings

---

### Obsidian Tracker

Project tracking, task management with kanban boards, bug logging, decision records (ADR), and session management via Obsidian. **Auto-tracks sessions, actions, bugs, and commits via hooks.**

📚 **[Full Documentation](plugins/obsidian-tracker/README.md)**

**Installation:**
```bash
/plugin install obsidian-tracker   # MCP server builds itself on first run
```

**Quick Start:**
```bash
/track-start my-project     # Start auto-tracking session
/projects                   # List all projects
/project-new                # Create new project
/task my-project "Fix bug"  # Create task on kanban board
/done my-project 1          # Mark task as done
/project-archive archive old-project  # Archive a project
/track-stop                 # Save session to Obsidian
```

**Status:** ✅ Production Ready | **Version:** 4.5.1

**What's New in 4.5.1:**
- Fix: MCP launcher installs deps when `dist/` ships prebuilt but `node_modules` is missing (was crashing the MCP server with -32000 / `ERR_MODULE_NOT_FOUND`).

**What's New in 4.5.0:**
- MCP server split into testable handler modules (83 vitest + 86 bats tests); auto-builds on first run — no manual `npm install && npm run build`.
- Task ids zero-padded (`TASK-007`, legacy unpadded still resolve); race-safe id allocation; session entry format shared between TS and bash via contract tests.

**What's New in 4.4.0:**
- Obsidian-safe filenames: titles are sanitized before becoming note names / wiki-links (mobile Obsidian and Sync no longer complain); `scripts/normalize-vault.mjs` renames existing offenders and fixes links.
- Board writes preserve `%% kanban:settings %%`, frontmatter, and custom sections; recursive `search`; several hook and parser fixes.

**Features:**
- Auto-tracking via hooks (PreCompact, SessionStart, PostToolUse)
- Project management with Obsidian as single source of truth
- Kanban task board with auto-increment IDs
- Project archiving and lifecycle management
- Bug tracking with priority levels
- Session logging (manual or automatic)

---

### Combined Review

Multi-agent code review with CodeRabbit CLI integration. 4 specialized agents + optional CodeRabbit for comprehensive review.

📚 **[Full Documentation](plugins/combined-review/README.md)**

**Installation:**
```bash
/plugin install combined-review
```

**Quick Start:**
```bash
/review                                    # Uncommitted changes
/review 123                                # GitHub PR / GitLab MR (forge auto-detected)
/review !22 +threads                       # GitLab MR + inline resolvable threads
/review feature/X feature/Y               # Branch diff
/review --base main                        # Current branch vs main
/review feature/X feature/Y +comments all # All agents
```

**Status:** ✅ Production Ready | **Version:** 1.4.0

**Features:**
- 4 default agents: code-reviewer, git-historian, silent-failure-hunter, test-analyzer
- CodeRabbit CLI integration (auto-install)
- Supports PR, branch diff, and uncommitted changes
- Confidence scoring (0-100) with false positive filtering
- Optional agents: +comments, +types, +simplify

---

### Auto Theme

Syncs Claude Code **and Codex** themes with macOS system appearance (light/dark) on every prompt. Bundles custom `gruvbox-light` / `sunset-drive` themes.

📚 **[Full Documentation](plugins/auto-theme/README.md)**

**Installation:**
```bash
/plugin install auto-theme
```

**Status:** ✅ Production Ready | **Version:** 1.1.2

**What's New in 1.1.2:**
- `sync-theme` skill now resolves the script path correctly in both Claude Code and Codex
- malformed config files and non-writable targets now emit `WARN:` instead of being skipped silently
- unknown `custom:*` themes without a light/dark pair are preserved instead of being overwritten

**What's New in 1.1.1:**
- `sync-theme` skill: explicit execution rules — macOS-only guard, stderr capture, write-protection and malformed-config errors, fixed 2-line response format

**What's New in 1.1.0:**
- Also themes Codex (`~/.codex/config.toml` `[tui] theme`), not just Claude Code
- Bundles + installs custom themes (`gruvbox-light`, `sunset-drive`) on first run
- Claude Code theme now read from `~/.claude/settings.json` (current CLI); `~/.claude.json` kept in sync
- Light↔dark pairing: `light → gruvbox-light`, `dark → sunset-drive`

**How it works:**
- Hooks into `UserPromptSubmit` — checks macOS appearance on every message
- Detects dark/light via `defaults read -g AppleInterfaceStyle`
- Claude Code: sets `theme` in `~/.claude/settings.json` (+ `~/.claude.json` mirror)
- Codex: sets `[tui] theme` in `~/.codex/config.toml` (register the hook once in `~/.codex/hooks.json`)
- Idempotent — no write when the theme already matches

---

### Locale Notifications

macOS notifications for Claude Code in your system language.

📚 **[Full Documentation](plugins/locale-notifications/README.md)**

**Installation:**
```bash
/plugin install locale-notifications
```

**Status:** ✅ Production Ready | **Version:** 2.0.1

**What's New in 2.0.1:**
- Quoted custom messages no longer break the macOS notification call
- Project-local config now resolves from the hook `cwd`
- Notification hook manifest now includes `timeout: 10`

**What's New in 2.0.0:**
- Auto-translation via Google Translate API — any language supported
- Local caching — one API call, then works offline
- Custom message support via config file

**How it works:**
- Hooks into Claude Code `Notification` events
- Detects system locale via `defaults read -g AppleLocale`
- Auto-translates and caches the notification message
- Displays native macOS notification via `osascript`

---

### Drawbridge

Bridge between a short brief and image-gen web UIs (Gemini Imagen 3, ChatGPT DALL-E 3, Grok Aurora, Midjourney). Crafts a target-tuned prompt, copies it to clipboard, opens the target — no API keys, no payments.

**What's New in 0.1.1:** frontmatter parsing no longer reopens on markdown `---` lines in the config body.

📚 **[Full Documentation](plugins/drawbridge/README.md)**

**Installation:**
```bash
/plugin install drawbridge
```

**Quick Start:**
```bash
/draw закат на байкале с медведем у воды        # default target from config
/draw -t midjourney cyberpunk samurai            # one-shot target override
/redraw -t chatgpt                               # variation of last brief, different target
/draw-prompt <brief>                             # prompt only, no browser open
/draw-config show                                # view defaults
/draw-config set default_target chatgpt          # change default
```

**Status:** 🔨 Beta | **Version:** 0.1.1

**Features:**
- Per-target prompt fine-tuning (Imagen prose / DALL-E structure / Aurora density / MJ tag syntax)
- Auto-translate brief to English (configurable)
- Settings via `~/.claude/drawbridge.local.md` with project-local override
- History of last 200 prompts for `/redraw`
- macOS only in 0.1.1

---

### Plugin Cross Port

Bridge between Claude Code and Codex plugin formats. One-shot conversion plus
deterministic dual-target marketplace reconciliation.

**[Full Documentation](plugins/plugin-cross-port/README.md)**

**Installation:**
```bash
/plugin install plugin-cross-port
```

**Quick Start:**
```bash
# Interactive (via skill)
Convert plugins/obsidian-tracker to Codex

# Attach and reconcile a marketplace
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace attach --source claude-code
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace sync
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace check

# Review and apply semantic adaptations
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin adapt plugins/example
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin adapt plugins/example --apply
```

**Status:** 🔨 Beta | **Version:** 0.10.1

**What's New in 0.10.1:**
- Fixed hand-authored `plugin-cross-port` skill frontmatter names to use kebab-case identifiers matching their directories

**What's New in 0.10.0:**
- **Breaking:** state files renamed to match their JSON content — `.plugin-cross-port.yaml` → `.plugin-cross-port.json`, `.plugin-cross-port.marketplace.yaml` → `.plugin-cross-port.marketplace.json`, `adaptation-state.yaml` → `adaptation-state.json`. Rename existing state files when upgrading.

**What's New in 0.9.0:**
- Agents auto-convert to standalone Codex skills (`agents/*.md` → `skills/generated-from-agents/<name>/SKILL.md`); CC `<example>` trigger blocks stripped from descriptions
- Fixed decision-file round-trip — `.plugin-cross-port.json` is written as JSON so re-runs no longer crash

**What's New in 0.8.0:**
- `skills_authored` marketplace flag — plugins whose Codex skills are hand-authored skip mechanical `commands/` → `skills/` generation (manifest + marketplace still synced)

**What's New in 0.7.0:**
- `plugin adapt` writes semantic adaptation plans and source snapshots
- `plugin adapt --apply` applies approved plans atomically
- Sync replays reproducible adaptation rules
- Stale critical adaptations mark Codex targets as unavailable

**Features:**
- CC → Codex: manifest conversion, `commands/` → `skills/generated-from-commands/`
- Codex → CC: manifest conversion, `skills/` → `commands/generated-from-codex-*/`
- Repository marketplace state plus per-plugin `.plugin-cross-port.json` source-of-truth
- Semantic adaptation plans for behavior that cannot be mechanically derived
- Generated output cleanup removes stale converted commands and skills
- Plugin-relative manual maintenance rules are honored in both directions
- Standalone converter scripts remain available for one-shot conversion

---

### Clip Maker

Automated vertical clip creator for talks and presentations. Whisper + Claude + ffmpeg pipeline.

📚 **[Full Documentation](plugins/clip-maker/README.md)**

**Installation:**
```bash
/plugin install clip-maker
```

**Quick Start:**
```bash
/clip-maker ~/Downloads/my-talk.mp4           # Full pipeline
/clip-maker ~/Downloads/my-talk.mp4 --auto    # Auto mode
/transcribe ~/Downloads/my-talk.mp4            # Only transcribe
/find-moments ~/Downloads/transcript.json      # Only find moments
```

**Status:** 🔨 Beta | **Version:** 1.3.1

**Features:**
- Whisper transcription (local or API)
- Opus-powered moment finding from transcript
- Vision-based smart crop (speaker detection)
- ffmpeg vertical clip cutting (9:16)
- Auto-subtitles from transcript
- Social media copy generation (Shorts/Reels/TikTok)

**What's New in 1.3.1:**
- Fixed dual-target agent naming for Claude Code pipeline calls
- Hardened script argument quoting, path handling, and ffmpeg/Whisper error surfacing

---

## Setup

After cloning, enable git hooks (runs plugin tests before push):

```bash
git config core.hooksPath .githooks
```

## Author

Ivan Lutsenko
GitHub: [@IvanLutsenko](https://github.com/IvanLutsenko)

## License

MIT - see [LICENSE](LICENSE)
