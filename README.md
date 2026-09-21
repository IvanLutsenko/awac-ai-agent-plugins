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

**Status:** ✅ Production Ready | **Version:** 4.4.5

**What's New in 4.4.5:**
- Quality gate tightened: `git fetch` alone no longer counts as evidence that the agent inspected the code. Forensics agents run it as a mandatory pre-flight on every run, so it proved nothing — `chk_executed_commands` now requires `git blame`, `git log` or `git ls-tree`.

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

**Status:** ✅ Production Ready | **Version:** 4.5.2

**What's New in 4.5.2:**
- Fix: the `PreCompact` hook never ran — it was a `prompt` hook, and those are rejected outside the REPL, so tracking state silently failed to survive `/compact`. Now a command hook that feeds the state to the compaction summarizer.
- Docs: hook table corrected against `plugin.json` (`Stop` and `SessionStart:clear` are command hooks; `PermissionRequest` was undocumented).

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

Multi-agent code review with CodeRabbit CLI integration. 5 specialized agents (security included by default) + optional CodeRabbit for comprehensive review.

📚 **[Full Documentation](plugins/combined-review/README.md)**

**Installation:**
```bash
/plugin install combined-review
```

**Quick Start:**
```bash
/review                                    # Uncommitted changes
/review 123                                # GitHub PR / GitLab MR (forge auto-detected)
/review 123 +threads                       # ...+ inline resolvable threads on the PR
/review !22 +threads                       # GitLab MR + inline resolvable threads
/review feature/X feature/Y               # Branch diff
/review --base main                        # Current branch vs main
/review feature/X feature/Y +security     # Add the security agent
/review feature/X feature/Y +comments all # All agents
/review-config                             # Language, model, CodeRabbit, security agent
/rereview 123 +resolve +approve            # Were my threads fixed? → resolve → approve (PR or MR)
```

**Status:** ✅ Production Ready | **Version:** 1.14.0

**What's New in 1.14.0:**
- All five agents always run — the `security` key and the `+security` flag are gone. Five agents cost about five times the tokens of a single pass, so the lever for cost is `model`, not a shorter roster (on Codex the model is set for the whole session instead).

**What's New in 1.12.2:**
- `/review` states what to do when the runtime has no per-agent model, no interactive prompt, or fewer concurrency slots than agents — instead of assuming Claude Code.

**What's New in 1.12.1:**
- Codex port fixed: helper scripts ship inside the generated skill, so `/review` run from Codex in another repo can actually find them (it could not — verified live).

**What's New in 1.12.0:**
- `filter-findings.py`: the scope check runs as a script you can re-run, printing KEEP / MOVED / DROP-with-reason / unparsed per finding instead of the model reporting that it filtered.

**What's New in 1.11.0:**
- No more confidence threshold: findings were filtered on a number each agent gave its own guess, which nothing in the report could verify. The scope map, the evidence rule and the falsifiability gate do the filtering; the bar is now one sentence in each agent — report only what you can defend from lines you read.
- Deduplication keeps the finding with the more specific evidence instead of the higher number.

**What's New in 1.10.2:**
- Findings must cite the line in the file, not a line of the diff — agents were quoting diff positions, which point past the end of short files.
- A finding whose file is in the position map but whose line is wrong is re-anchored by grepping the quoted code, instead of being dropped as out of scope.

**What's New in 1.10.1:**
- The scope filter's position map is built by `python3` instead of `awk` — argument substitution in the command text turned `$0` into an argument value, so the map lost every file name and the review silently dropped all findings.
- `[SEEN]` removed: an existing thread on a line blocks a second one whoever wrote it, so the author check and the ticket regex went with it.
- `security-reviewer` now follows the report language setting like the other four agents.
- The security agent is agent 5 and CodeRabbit agent 6 everywhere, as the config docs already said.

**What's New in 1.10.0:**
- GitHub parity: `+threads` posts inline resolvable review comments on a PR, and `/rereview` verifies, resolves (GraphQL `resolveReviewThread`) and approves a PR — previously GitLab-only.
- GitHub PRs are now fetched by `refs/pull/<n>/head`, so a PR from a fork is diffed and read at the right revision instead of failing on a branch that isn't in `origin`.
- Fixed three defects from 1.9.0: the scope filter no longer discards every finding when the position map can't be built, a worktree that can't be checked out stops the review instead of quietly reviewing cwd, and the documented MR fetch command now names a remote git actually accepts.

**What's New in 1.9.0:**
- GitLab MR review now fetches by ref (works for forks/cross-project MRs), reads the reviewed revision in a worktree instead of cwd, and dedupes/pins posted threads to that revision.
- Dropped the Android-only assumptions (test convention, `gh` call, Kotlin-only examples); race findings now need a causal gate, not just a timing gap.

**What's New in 1.8.0:**
- `security-reviewer` agent — secrets, injection, authn/authz, insecure storage and transport, unsafe crypto; stack-agnostic, opt-in via `+security`.
- `/review-config` — interactive setup for report language, subagent model, CodeRabbit and the security agent.
- Config moved out of the plugin: `~/.claude/combined-review.md` (user-level) plus the existing project file, so settings survive updates.

**What's New in 1.7.1:**
- Docs: the GitLab project-path example no longer names a specific private project.

**What's New in 1.7.0:**
- Falsifiability gate on every Critical (safe / intended / already-mitigated / weak evidence) — findings must survive an attempt to refute them, not just an attempt to confirm them.
- Out-of-diff claims must quote the caller or contract they rest on.

**What's New in 1.6.0:**
- `/rereview +agents` — one agent per file (auto above ~8 files); agents see the asks and the code, not the author's replies, so a plausible-looking diff can't pass as a fix by association.

**What's New in 1.5.0:**
- `/rereview` — verifies your unresolved GitLab MR threads against the code at the MR head, then (opt-in) resolves them and approves. Author replies and GitLab's "changed this line in version N" auto-note don't count as a fix.

**Features:**
- 4 default agents: code-reviewer, git-historian, silent-failure-hunter, test-analyzer
- CodeRabbit CLI integration (auto-install)
- Supports GitHub PR, GitLab MR (inline threads), branch diff, and uncommitted changes
- `/rereview` follow-up: per-thread fixed/not-fixed verdicts, resolve + approve
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

**Status:** 🔨 Beta | **Version:** 0.12.0

**What's New in 0.12.0:**
- Converted command skills end with a `## Codex differences` section listing the CC assumptions Codex cannot honour — per-agent model, true parallelism, interactive prompts.

**What's New in 0.11.0:**
- Generated Codex skills carry their helper scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/...` became a path that only resolved inside this marketplace, so a converted skill run from Codex in another repo could not find its own helpers.

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
