# Crashlytics Plugin

Crash log analysis with root cause identification, code-level fixes, and developer assignment via git blame.

**Version:** 4.4.4 — Android & iOS

---

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install crashlytics
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add crashlytics@awac-ai-agent-plugins
```

See [Prerequisites](#prerequisites) below for the runtime dependencies the
plugin checks on first run (Node.js, Firebase access, etc.).

After updating to 4.4.4, restart the Claude Code session once so the pinned MCP launcher in `.mcp.json` is reloaded.

---

## Prerequisites

> **The plugin checks prerequisites automatically** on every run and shows what's missing.
> If something is missing, it will show install instructions and offer to fix what it can.

### Required (without these the plugin won't analyze code)

- **Git** — repository with commit history
- **Claude Code** with the `crashlytics` plugin installed

### Required for automatic crash data loading

| # | Dependency | Install command | What it does |
|---|-----------|----------------|-------------|
| 1 | **Node.js** | `brew install node` (macOS) / `sudo apt install nodejs` (Linux) | Runtime for Firebase MCP server and CLI |
| 2 | **firebase-tools** | `npm install -g firebase-tools` | Firebase CLI — project discovery + auth token |
| 3 | **Firebase login** | `firebase login` (opens browser) | Creates token at `~/.config/configstore/firebase-tools.json` |
| 4 | **python3** | Usually pre-installed on macOS/Linux | Runs the REST API script to fetch crash data |
| 5 | **Crashlytics API** | Enable in [GCP Console](https://console.cloud.google.com/apis/library/firebasecrashlytics.googleapis.com) | Without this, REST API returns 403 |

### Quick setup (copy-paste)

```bash
# 1. Install firebase-tools (requires Node.js)
npm install -g firebase-tools

# 2. Login (opens browser)
firebase login

# 3. Set active project
firebase use your-project-id

# 4. Enable Crashlytics API (replace YOUR_PROJECT_ID)
# Option A: open in browser
open "https://console.cloud.google.com/apis/library/firebasecrashlytics.googleapis.com?project=YOUR_PROJECT_ID"
# Option B: via gcloud (if installed)
gcloud services enable firebasecrashlytics.googleapis.com --project=YOUR_PROJECT_ID
```

> **Without Firebase setup** the plugin still works — but in Manual mode (you paste the stack trace yourself).

### One-time permission allowlist (recommended)

After install, run once to add the plugin's read-only git/MCP calls to your settings.json — eliminates permission prompts during `/crash-report`:

```bash
/crashlytics:install-permissions
```

The command is interactive: pick user-level (`~/.claude/settings.json`) or project-level scope, see the exact diff, confirm. Adds only read-only operations (git status/log/blame/diff/show/fetch/ls-tree, validate-report.py, MCP `crashlytics_get_*`/`firebase_get_*`/`firebase_list_*`). Never adds write/auth/destructive rules.

---

## Quick Start

### Unified command (recommended)

```bash
/crash-report ca8f7f21e3ec633d0d1dca453409435b
```

Auto-detects platform from config. Accepts issue ID, console URL, or stack trace.

### Platform-specific

```bash
/crash-report-android              # Explicit Android
/crash-report-ios                  # Explicit iOS
```

### Configure the plugin

```bash
/crash-config
```

Interactive setup for language, branch, model, output format, and Firebase project.
Config auto-created with defaults on first run if missing.

---

## Operating Modes

| Mode | Requirements | What you get |
|------|-------------|--------------|
| **MCP fast-path** | Firebase Issue ID + `firebase login` + project_id/app_id in config | Direct `crashlytics_get_issue` + `crashlytics_batch_get_events` calls — no agent hop |
| **MCP via firebase-fetcher** | Firebase Issue ID + `firebase login` (no config) | Discovery via `firebase_get_environment`/`firebase_list_apps`, then crash data via MCP |
| **REST fallback** | Same as MCP but MCP errors out | `python3 fetch-crash-data.py` against the v1alpha REST API (Crashlytics API must be enabled) |
| **Enhanced Manual** | Stack trace from logs | Same analysis, guided manual data entry with Console URLs |

The plugin tries paths in order: MCP fast-path → MCP via fetcher → REST fallback → Enhanced Manual.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                      crashlytics v4.4.4                         │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
     ┌─────────────────┐            ┌─────────────────┐
     │   Android        │            │      iOS        │
     │   /crash-report  │            │  /crash-report  │
     │   -android       │            │      -ios       │
     ├─────────────────┤            ├─────────────────┤
     │ classifier       │            │  classifier     │
     │ firebase-fetcher │            │  firebase-fetcher│
     │ forensics        │            │  forensics      │
     │ reviewer         │            │  reviewer       │
     └─────────────────┘            └─────────────────┘
```

### Four-step analysis

1. **Classifier** (Haiku) — determines component and trigger
2. **Firebase Fetcher** (Haiku) — loads data via CLI REST API (MCP for discovery only)
3. **Forensics** (Opus) — git blame + code-level fix + assignee
4. **Reviewer** (Haiku) — quality gate validating all mandatory fields

---

## Commands

| Command | Platform | Description |
|---------|----------|-------------|
| `/crash-report` | Auto | Unified command — auto-detects platform from config |
| `/crash-report-android` | Android | Analyze Kotlin/Java crashes |
| `/crash-report-ios` | iOS | Analyze Swift/Objective-C crashes |
| `/crash-config` | Both | Interactive plugin configuration |

---

## Configuration

Run `/crash-config` to set up:

| Setting | Default | Description |
|---------|---------|-------------|
| `language` | English | Output language |
| `default_branch` | master | Branch for git blame |
| `default_platform` | android | Default platform |
| `forensics_model` | opus | Model for forensics agent (opus/sonnet/haiku) |
| `output_format` | both | Output: both / detailed_only / jira_only |
| `firebase_project_id` | — | Firebase project ID (skip auto-detection) |
| `firebase_app_id_android` | — | Android app ID |
| `firebase_app_id_ios` | — | iOS app ID |

Config is stored in `.claude/crashlytics.local.md` (per-project, gitignored).

---

## Input Data

| Field | Required | Description |
|-------|----------|-------------|
| Stack trace | Yes | From Firebase Crashlytics or logs |
| Firebase Issue ID | No | For automatic data loading |
| Crash count | No | Context for analysis |
| % users | No | Context for analysis |
| Device / OS | No | Context |

---

## Output

The plugin returns two formats:

### 1. Detailed Analysis

```
### Crash: NullPointerException in PaymentProcessor

**Basic info**:
- Exception: NullPointerException
- Affected users: 8%
- App version: 2.5.0
- Component: payments

**Stack trace analysis**:
- PaymentProcessor.processPayment():45
- PaymentFragment.onPayClicked():89

**Checked files**:
- src/main/java/.../PaymentProcessor.java:45
  Author: John Smith (git blame)
  Commit: a1b2c3d4

**Executed commands**:
- git blame master -- PaymentProcessor.java -L 40,50
- git log master --oneline -10 -- PaymentProcessor.java

**Root cause**:
paymentProcessor not initialized before calling processPayment()

**Proposed fix**:
Before:
  paymentProcessor.processPayment(card);

After:
  paymentProcessor?.processPayment(card)
    ?: logError("PaymentProcessor not initialized")

**Assignee**: John Smith
- Source: git blame line 45 showed: John Smith

**Context & Prevention**:
- Trigger: User tapped "Pay" button
- Why now: Initialization order changed in v2.5.0
- Prevention: Add null check or lateinit validation
```

### 2. JIRA Brief

Compact format for copy-paste into a ticket, including stack trace, fix (before/after), reproduction steps, and Firebase console link.

---

## Firebase Integration

### Setup

1. Check `.mcp.json` in the plugin:
   ```json
   {
     "mcpServers": {
       "firebase": {
         "command": "sh",
         "args": ["-c", "NODE_OPTIONS='--max-old-space-size=4096' npx -y firebase-tools@15 mcp"]
       }
     }
   }
   ```

2. Authorize:
   ```bash
   firebase login
   ```

3. Set active project:
   ```bash
   firebase use your-project-id
   ```

4. **Enable Crashlytics API** (required for REST API data fetch):
   - GCP Console: `https://console.cloud.google.com/apis/library/firebasecrashlytics.googleapis.com?project=YOUR_PROJECT_ID`
   - Or via gcloud: `gcloud services enable firebasecrashlytics.googleapis.com --project=YOUR_PROJECT_ID`

### What firebase-fetcher loads

- Issue details (title, status, event count)
- Sample events with full stack traces
- Device info (model, OS version)
- App version

### How data fetching works

The plugin uses a multi-level fallback:
1. Fetches crash data via **CLI REST API** (`v1alpha`) using the token from `~/.config/configstore/firebase-tools.json`
2. Falls back to **MCP Crashlytics tools** (`crashlytics_list_events`, `crashlytics_get_issue`, `crashlytics_batch_get_events`)
3. Falls back to **Enhanced Manual mode** with Console URLs and step-by-step instructions

MCP is also used for **project/app discovery** (`firebase_get_environment`, `firebase_list_apps`).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| REST API returns 403 | Crashlytics API not enabled. Enable at: `https://console.cloud.google.com/apis/library/firebasecrashlytics.googleapis.com?project=YOUR_PROJECT_ID` |
| "Unable to verify client" | Do not use MCP login. Authorize via `firebase login` in terminal |
| MCP Internal error | Normal for discovery — plugin retries once then uses CLI fallback |
| `REST_FALLBACK_FAILED` | Check `firebase login:list` — may need to re-authenticate |
| "Files not found" | Make sure you're in the git repository root |
| "git blame not working" | Check that the repository has commit history |
| "Assignee = TBD" | Manual ownership analysis required |

---

## Changelog

### 4.4.4
- **Fixed:** `.mcp.json` now launches Firebase MCP via `firebase-tools@15` instead of `@latest`, so session startup no longer depends on whatever major npm serves that day.
- **Doc:** added an explicit note that changing `.mcp.json` requires a Claude Code session restart before the new MCP command is used.

### 4.4.3
- **Changed:** forensics-agents теперь пишут section headers всегда на английском, body content — на target language. Validator больше не зависит от языка отчёта (Language Policy block в обоих forensics-android.md / forensics-ios.md).
- **Fixed:** validator выдавал false 6/14 на отчётах не на английском — добавлен `SECTION_ALIASES` dict с переводами для en, ru, es, de, fr, pt, it. Aliases — safety-net для случаев, когда LLM всё-таки переведёт заголовок. Расширяется одной строкой в dict.
- **Fixed:** `split_sections` теперь распознаёт bold-only header lines (`**Basic info:**`, `**Базовая информация:**`) — это позволяет валидировать subsections внутри `### Crash:` parent блока.
- **Fixed:** forensics-android/ios хардкодили `master` в командах git blame — false-negative когда локальный master отставал от origin/master. Теперь все git операции через `BRANCH_REF` (= `origin/<default_branch>`), обязательный `git fetch origin --quiet` перед blame/log/show.
- **Added:** STEP 4.0 sanity-check «is the fix already merged?» — `git log BRANCH_REF --grep="<TICKET-ID>"` + `git ls-tree BRANCH_REF -- <new-path>`. Если fix уже в BRANCH_REF, отчёт указывает это вместо ложного «fix не написан».
- **Added:** smoke tests для validator на 7 языках (en/ru/es/de/fr/pt/it) в `scripts/tests/`. `bash scripts/tests/run-tests.sh` — должно быть `All 7 fixtures passed.`
- **Added:** `/crashlytics:install-permissions` — интерактивная команда, которая мерджит read-only git/MCP вызовы плагина в `~/.claude/settings.json` или `.claude/settings.local.json` (на выбор), чтобы `/crash-report` не прерывался на approval'ах.
- **Changed:** `allowed-tools:` в `crash-report.md`/`-android.md`/`-ios.md` расширен на `git fetch/ls-tree/ls-files/rev-parse/merge-base/branch/remote`, `test`, `touch`, и read-only MCP `crashlytics_*`/`firebase_get_*`/`firebase_list_*` — auto-allow на время выполнения команды.
- **Changed:** Skill instruction для `pass: false` теперь 3-way: per-section fill / language-false-positive recheck / generic fill.
- **Changed:** `/crash-config` подсказывает, что `default_branch` — local branch name; плагин использует `origin/<this>` для git blame.

### 4.4.2
- **Fixed:** `firebase-fetcher` agent had no MCP tools in its `tools:` list and could not execute the "MCP discovery" path documented in its prompt — added `mcp__plugin_crashlytics_firebase__*` tools explicitly
- **Changed:** MCP is now the primary fetch path (`crashlytics_get_issue` + `crashlytics_batch_get_events`); REST `v1alpha` becomes a true fallback. `/crash-report` and platform-specific commands gained a "Path A: direct MCP fast-path" that skips the agent hop when project_id/app_id are in config
- **Fixed:** Quality gate now writes the forensics report to `/tmp/crashlytics-forensics-{ISSUE_ID}.md` and pipes via stdin redirect — `echo "..."` was mangling backticks/`$`/code fences in long reports and producing false 1/14 validation results
- **Doc:** added explicit warning to never re-validate against an abbreviated summary on `pass: false`

### 4.4.1
- **Fixed:** `validate-report.py` — синхронизирован список `VALID_COMPONENTS` с фактическими компонентами, корректное чтение `console_url`
- **Fixed:** iOS документация — мелкие правки

### 4.4.0
- **Fixed:** REST API version `v1beta1` → `v1alpha` (root cause of all 404 errors)
- **Fixed:** Events endpoint `/issues/{id}/events` → `/events?filter.issue.id={id}` (correct v1alpha format)
- **Added:** Auto-save discovered `firebase_app_id` to config after successful fetch — eliminates repeated discovery
- **Fixed:** MCP crash tools (`crashlytics_list_events`, `crashlytics_get_issue`, `crashlytics_batch_get_events`) DO work — restored as fallback

### 4.3.1
- Added `Grep`, `Agent`, `Bash(git diff:*)`, `Bash(git show:*)` to `allowed-tools` in all crash-report commands — forensics agents and code search no longer require manual approval

### 4.2.3
- **Refactor:** Extracted inline bash/python into `scripts/check-prerequisites.sh` and `scripts/fetch-crash-data.py` — eliminates Claude Code security prompts for `$()` substitution and `f"...{}"` patterns
- **Changed:** All 4 files (crash-report, crash-report-android, crash-report-ios, firebase-fetcher) now call external scripts instead of inline heredocs

### 4.2.2
- **Fixed:** Added `Bash(echo:*)` to `allowed-tools` in all crash-report commands — prerequisites check no longer requires manual approval

### 4.2.1
- **Added:** Automatic prerequisites check on every `/crash-report` run (Node.js, firebase-tools, auth, python3)
- **Added:** Auto-install offer for firebase-tools if npm is available
- **Added:** Detailed setup instructions in README with copy-paste commands
- Plugin degrades gracefully: missing tools → Manual mode instead of cryptic errors

### 4.3.0
- **Breaking:** Replaced `report-reviewer` Haiku agent with `validate-report.py` deterministic script
- Quality gate now runs in ~0.05s instead of ~3-5s, zero token cost
- 11/14 structural checks are definitive (regex/pattern matching)
- 3 semantic checks (Root cause, Trigger, Why now) use word-count heuristics — flagged as `needs_review` for the calling command to decide
- `pass: null` state: script can't decide → command LLM evaluates (zero extra cost, already in context)
- Removed `report-reviewer.md` agent

### 4.2.0
- **Breaking:** Removed non-existent MCP Crashlytics data tools (`crashlytics_get_issue`, `crashlytics_list_events`, `crashlytics_batch_get_events`, `crashlytics_get_report`) — these were never implemented in Firebase MCP server
- **Changed:** 3-level → 2-level fallback: CLI REST API → Enhanced Manual
- **Changed:** MCP now used only for project/app discovery (working tools: `firebase_get_environment`, `firebase_list_apps`)
- **Changed:** firebase-fetcher agent rewritten: `tools: Bash, Read` instead of `ListMcpResourcesTool, ReadMcpResourceTool`
- **Added:** API_NOT_ENABLED detection with enable instructions (GCP Console URL + gcloud command)
- **Added:** Enhanced Manual fallback with step-by-step Console instructions
- **Added:** Prerequisites: Crashlytics API must be enabled in GCP
- **Fixed:** 4.1.1 changelog (previously claimed MCP tools work — they don't)

### 4.1.1
- **Fix:** `experimental:mcp` → `mcp` — Firebase MCP graduated to GA, old command didn't register tools
- Updated troubleshooting: removed obsolete `experimental:mcp` references
- Note: this fixed MCP discovery tools but Crashlytics data tools were never available

### 4.1.0
- Unified `/crash-report` command — auto-detects platform from config
- Config auto-created with defaults on first run (no more manual setup required)
- MCP retry-first strategy: retries up to 2 times before REST API fallback
- REST API fallback: single script, token never printed to stdout
- Fixed `firebase projects:list` JSON parsing for different CLI versions
- Removed duplicate REST code from Step 3

### 4.0.0
- Quality gate: `validate-report.py` script validates all mandatory fields before output
- Interactive `/crash-config` command for plugin configuration
- Default forensics model changed to Opus (Sonnet as fallback)
- Severity/priority removed from classifiers — forensics handles context
- Full English translation of all agents and commands
- Configuration system via `.claude/crashlytics.local.md`
- `console_url` and `branch` passed explicitly to forensics agents
- Mandatory "Executed commands" section in detailed analysis
- Mandatory "Context & Prevention" (Trigger, Why now, Prevention)
- Mandatory reproduction steps and Firebase link in JIRA Brief

### 3.2.0
- 3-level Firebase fallback: MCP → CLI API (token from firebase-tools.json) → Console URL + manual input
- Blocked `firebase_login` via MCP (broken: "Unable to verify client")
- `allowed-tools` for automatic approval of Firebase CLI and curl/python3 commands
- Auto-load data by Issue ID without manual stack trace input

### 3.1.0
- Multi-agent architecture: classifier → firebase-fetcher → forensics
- iOS support

### 3.0.0
- Initial release with Android & iOS support

---

## License

MIT
