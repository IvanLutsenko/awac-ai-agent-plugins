# AWAC AI Agent Plugins

Custom AI agent plugins by Ivan Lutsenko

## Contents

- [Installation](#installation)
  - [Claude Code](#claude-code)
  - [Codex CLI](#codex-cli)
- [Available Plugins](#available-plugins)
  - [Engineering quality](#engineering-quality)
    - [Crashlytics](#crashlytics) — Android/iOS crash analysis with git blame forensics
    - [Combined Review](#combined-review) — multi-agent code review + CodeRabbit, PR/MR threads
  - [Workflow](#workflow)
    - [Obsidian Tracker](#obsidian-tracker) — projects, kanban, bugs, ADR and sessions in Obsidian
    - [Plugin Cross Port](#plugin-cross-port) — Claude Code ↔ Codex plugin conversion
    - [Push Gate](#push-gate) — confirm every `git push` the model runs (mod)
  - [Environment & media](#environment--media)
    - [Auto Theme](#auto-theme) — Claude Code and Codex theme follows macOS light/dark
    - [Locale Notifications](#locale-notifications) — macOS notifications in your system language
    - [Drawbridge](#drawbridge) — target-tuned prompts for image-gen web UIs
    - [Clip Maker](#clip-maker) — vertical clips from talk recordings
    - [Talk Deck](#talk-deck) — themed talk decks on top of Craft
    - [Nyan Progress](#nyan-progress) — Nyan Cat over the turn spinner (mod)
- [Contributing](#contributing)
- [Author](#author)
- [License](#license)

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

> Codex caveat: `locale-notifications`, `nyan-progress` and `push-gate` are
> Claude Code-only (excluded from the Codex target). The last two are mods built
> on Claude Code function hooks.

## Available Plugins

### Engineering quality

#### Crashlytics

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
```

**Status:** ✅ Production Ready | **Version:** 4.4.7

**What's New in 4.4.7:**
- Quality gate: the forensics agent writes its full report to a file, and the validator checks that file — the orchestrator no longer retypes the report. No manual pass on a failed validation. The validator now reads `**Assignee**: value` lines and `File.kt:77` stack lines, which failed full live reports.

**Features:**
- 4-step multi-agent pipeline: classifier → fetcher → forensics → validate-report.py
- Git blame forensics with mandatory assignee identification, on `origin/<default_branch>`
- Code-level fixes (before/after) ready to copy-paste
- MCP-primary fetch (`crashlytics_get_issue` + `crashlytics_batch_get_events`), REST `v1alpha` fallback, Manual mode for offline use
- Multi-language reports (English headers + body in any language)
- Configurable per-project settings


---

#### Combined Review

Multi-agent code review with CodeRabbit CLI integration. 5 specialized agents — security included, no per-agent switches — plus CodeRabbit, a third-party reviewer that reads the same diff independently. CodeRabbit uploads the diff to its own servers; `coderabbit: off` keeps the review entirely local.

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
/review feature/X feature/Y +comments     # Add an optional agent (+comments, +types, +simplify)
/review feature/X feature/Y all           # All agents, optional ones included
/review-config                             # Language, model, CodeRabbit, second vendor
/rereview 123 +resolve +approve            # Were my threads fixed? New code ok? → resolve → approve (PR or MR)
```

**Status:** ✅ Production Ready | **Version:** 1.21.1

**What's New in 1.21.1:**
- `/rereview` lifts your own GitLab «Request changes» after a successful approve; an approval alone left the MR blocked.

**What's New in 1.21.0:**
- CodeRabbit findings no longer vanish: every one goes through the same filter as the agents', and the report counts them and lists each dropped one with a reason.
- The report ends on the author's name and login, not the login alone.
- `/rereview` counts the new-code pass as done only when all five agents ran on it; reading the commits in the main loop is not the pass, and approval is held back otherwise.
- The second vendor no longer forces `model_reasoning_effort=high`; new `vendor_model` / `vendor_effort` keys pick a cheaper model and effort for the review pass.

**What's New in 1.20.0:**
- `security-reviewer` also looks for weakened tamper defences (root/jailbreak, integrity and anti-fraud checks bypassed or gated on a flag that can reach release), web-view bridges open to any origin, sensitive screens left capturable, and biometric fallbacks that look accidental. Worded per class, not per stack.

**What's New in 1.19.0:**
- `/rereview` now also reviews the code added since your last review — a full `/review` pass limited to the new lines — so `+approve` no longer approves code nobody read. A finding there holds back the approval; `-new` skips the pass.

**What's New in 1.18.2:**
- The second-vendor pass now runs until 10 minutes after the other agents finish instead of a fixed 10 minutes from launch, so a long review on a big MR is not cut while the rest of the review is still working. Its child processes are stopped with it.

**What's New in 1.18.1:**
- The second-vendor pass is locked down further: `codex exec` starts from a temp dir with `--ignore-rules`, so the reviewed branch's `.codex/` config, MCP servers and rules never load; `claude -p` runs with `--restricted`, so it reads nothing outside the repository. Both CLIs are capped at 10 minutes, and only a run that exits 0 with findings or a final `clean` counts — anything else is `unavailable`.

**What's New in 1.18.0:**
- `second_vendor: auto` adds one pass by the other vendor's CLI — `codex exec` when `/review` runs in Claude Code, `claude -p` when it runs in Codex. Off by default: the diff goes to that vendor under the reviewer's own subscription. A missing CLI, a timeout or a quota error shows as `unavailable` in the report and never fails the review.

**What's New in 1.17.1:**
- `/review` and `/rereview` end the report with the PR/MR author and a link to it, so a review running in a side pane says whom the findings go to and where.

**What's New in 1.17.0:**
- `/review` sends findings on generated lines to the generator, not the author; `/rereview` flags threads whose reply says "fixed" while the code says not (🚩), first in the report and blocking resolve/approve.

**Features:**
- 5 agents always run: code-reviewer, git-historian, silent-failure-hunter, test-analyzer, security-reviewer
- CodeRabbit CLI integration (installed on consent; `coderabbit: off` keeps the review local)
- Supports GitHub PR, GitLab MR (inline threads), branch diff, and uncommitted changes
- `/rereview` follow-up: per-thread fixed/not-fixed verdicts, resolve + approve
- Findings filtered by scope map, evidence rule and falsifiability gate (`filter-findings.py`)
- Optional agents: +comments, +types, +simplify


### Workflow

#### Obsidian Tracker

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

**Status:** ✅ Production Ready | **Version:** 4.5.4

**What's New in 4.5.4:**
- Codex: the generated skills are rebuilt by the current converter. Helper scripts now ship inside each skill and are called as `<this skill directory>/scripts/...`, not through repo-relative `plugins/obsidian-tracker/scripts/...` paths that do not exist once the plugin is installed. Command skills end with a `## Codex differences` note. Claude Code behaviour is unchanged.

**Features:**
- Auto-tracking via hooks (PreCompact, SessionStart, PostToolUse)
- Project management with Obsidian as single source of truth
- Kanban task board with auto-increment IDs
- Project archiving and lifecycle management
- Bug tracking with priority levels
- Session logging (manual or automatic)


---

#### Plugin Cross Port

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

**Status:** 🔨 Beta | **Version:** 0.12.2

**What's New in 0.12.2:**
- `skills_authored` now covers agents too. A plugin whose Codex skills are hand-written got its agents generated as Codex skills anyway (only command skills were skipped), so they sat beside the authored ones and duplicated them. Both are skipped now, and the generated folders are removed.

**Features:**
- CC → Codex: manifest conversion, `commands/` → `skills/generated-from-commands/`
- Codex → CC: manifest conversion, `skills/` → `commands/generated-from-codex-*/`
- Repository marketplace state plus per-plugin `.plugin-cross-port.json` source-of-truth
- Semantic adaptation plans for behavior that cannot be mechanically derived
- Generated output cleanup removes stale converted commands and skills
- Plugin-relative manual maintenance rules are honored in both directions
- Standalone converter scripts remain available for one-shot conversion


---

#### Push Gate

Asks before every `git push` the model runs, in Claude Code's own question dialog. A click confirms that one command; anything else refuses it. A mod: built on function hooks (early access).

📚 **[Full Documentation](plugins/push-gate/README.md)**

**Installation:**
```bash
/plugin install push-gate
```

**Status:** 🔨 Beta | **Version:** 0.2.0

**Features:**
- Catches every spelling of a push: `bash -c`, subshells, `/usr/bin/git`, `env`/`command` prefixes, global options (`-C`, `-c`), multi-line commands; `push` in a path or a grep pattern is not a push
- Only asks, never allows: the auto mode classifier still judges the push
- Optional one-shot token for a PreToolUse guard, so the guard stays safe when mods are off


### Environment & media

#### Auto Theme

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

**How it works:**
- Hooks into `UserPromptSubmit` — checks macOS appearance on every message
- Detects dark/light via `defaults read -g AppleInterfaceStyle`
- Claude Code: sets `theme` in `~/.claude/settings.json` (+ `~/.claude.json` mirror)
- Codex: sets `[tui] theme` in `~/.codex/config.toml` (register the hook once in `~/.codex/hooks.json`)
- Idempotent — no write when the theme already matches


---

#### Locale Notifications

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

**How it works:**
- Hooks into Claude Code `Notification` events
- Detects system locale via `defaults read -g AppleLocale`
- Auto-translates and caches the notification message
- Displays native macOS notification via `osascript`


---

#### Drawbridge

Bridge between a short brief and image-gen web UIs (Gemini Imagen 3, ChatGPT DALL-E 3, Grok Aurora, Midjourney). Crafts a target-tuned prompt, copies it to clipboard, opens the target — no API keys, no payments.

**What's New in 0.1.2:** Codex: the generated skills are rebuilt by the current converter. Helper scripts now ship inside each skill and are called as `<this skill directory>/scripts/...`, not through repo-relative `plugins/drawbridge/scripts/...` paths that do not exist once the plugin is installed. Command skills end with a `## Codex differences` note. Claude Code behaviour is unchanged.

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

**Status:** 🔨 Beta | **Version:** 0.1.2

**Features:**
- Per-target prompt fine-tuning (Imagen prose / DALL-E structure / Aurora density / MJ tag syntax)
- Auto-translate brief to English (configurable)
- Settings via `~/.claude/drawbridge.local.md` with project-local override
- History of last 200 prompts for `/redraw`
- macOS only in 0.1.2


---

#### Clip Maker

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

**Status:** 🔨 Beta | **Version:** 1.3.2

**Features:**
- Whisper transcription (local or API)
- Opus-powered moment finding from transcript
- Vision-based smart crop (speaker detection)
- ffmpeg vertical clip cutting (9:16)
- Auto-subtitles from transcript
- Social media copy generation (Shorts/Reels/TikTok)

**What's New in 1.3.2:**
- Codex: the generated skills are rebuilt by the current converter. Helper scripts now ship inside each skill and are called as `<this skill directory>/scripts/...`, not through repo-relative `plugins/clip-maker/scripts/...` paths that do not exist once the plugin is installed. Command skills end with a `## Codex differences` note. Claude Code behaviour is unchanged.


---

#### Talk Deck

Talk decks on top of the [Craft](https://github.com/IvanLutsenko/craft) skill: a fresh holiday theme per talk, the author's defaults, a themed Harold on the closing slide, a PDF for organizers and a card on the author's site.

**What's New in 0.6.0:** `/deck-new` may offer one or two signature SVG scenes for claims the audience would underestimate, built only on the author's pick. 0.5.1: `/deck-publish --public` takes a deck published with `--hidden` onto the site. 0.5.0: `/deck-google-slides` in 2x with counters as GIFs and `--update` in place, so transitions and the organizer's copy survive; `/deck-publish --hidden` for a deck reachable by link only.

📚 **[Full Documentation](plugins/talk-deck/README.md)**

**Installation:**
```bash
/plugin install talk-deck
```

**Quick Start:**
```bash
/deck-new CI/CD in a bank --date 2026-12-20     # themed deck for the nearest holiday
/deck-harold                                    # brief for the themed Harold via drawbridge
/deck-harold place                              # downloaded picture onto the closing slide
/deck-pdf --final                               # PDF for organizers
/deck-pdf --into docs/deck                      # PDF into a repo, with its GitLab/GitHub link
/deck-google-slides [--steps] [--update]        # 2x frames or every reveal step into Google Slides, update in place
/deck-review                                    # roast by every agent, facts checked first
/deck-rehearse 22                               # rehearsal timer, time per slide against the plan
/deck-publish --event "Podlodka #17"            # card on the author's site, no push; --hidden for link-only
```

**Status:** 🔨 Beta | **Version:** 0.6.0

**Features:**
- Needs the Craft skill; the plugin holds only commands and a hook
- Settings via `~/.claude/talk-deck.local.md`: author, contact, language, site repo
- PostToolUse hook runs the static Craft check after edits inside a deck (Claude Code only)
- `/deck-google-slides` needs the `google-workspace-unlimited` MCP server and `ffmpeg`; the files are link-readable for the seconds of insertion, then deleted; GIFs play only in a plain slideshow


---

#### Nyan Progress

Nyan Cat and a rainbow across the whole terminal width over Claude Code's turn spinner, while a turn runs. The real picture where the terminal draws images (kitty, Ghostty); a braille outline with dotted speed lines elsewhere, or colour pixels on request. A mod: built on function hooks (early access).

![nyan-progress](plugins/nyan-progress/docs/gif.gif)

📚 **[Full Documentation](plugins/nyan-progress/README.md)**

**Installation:**
```bash
/plugin install nyan-progress
```

**Quick Start:**
```bash
/nyan            # show the current look
/nyan gif        # the real picture, 2 rows (falls back to dots where images don't draw)
/nyan pixel      # the sprite in colour cells, any truecolor terminal
/nyan dots       # the outline in braille with rainbow-dotted speed lines, 5 rows
```

**Status:** 🔨 Beta | **Version:** 0.1.1

**Features:**
- The original gif's 12 frames, and a waving rainbow as wide as the terminal
- Animation paced to the engine's spinner repaint cap, so it does not stutter at the start of a turn
- Fan project: Nyan Cat © Chris Torres; MIT covers the code only


## Contributing

For working on the plugins in a clone of this repo; installing them needs
none of this. Enable the repo's git hooks once after cloning:

```bash
git config core.hooksPath .githooks
```

- `pre-commit` regenerates the Codex targets (`plugin-cross-port`) of the
  plugins you changed and stages them.
- `pre-push` runs the `obsidian-tracker` tests when that plugin is in the
  push (bats and vitest; each is skipped with a warning when `bats` or
  `mcp/node_modules` is missing) and refuses the push when a changed
  `obsidian-tracker` source file has no test. Other plugins' tests are not
  wired into the hook.

## Author

Ivan Lutsenko, Android Tech Lead at Bereke Bank

- Site: [ivan.nullptr.party](https://ivan.nullptr.party)
- Telegram: [@maliastra](https://t.me/maliastra)
- LinkedIn: [ivan-lutsenko](https://www.linkedin.com/in/ivan-lutsenko/)
- GitHub: [@IvanLutsenko](https://github.com/IvanLutsenko)

## License

MIT - see [LICENSE](LICENSE)
