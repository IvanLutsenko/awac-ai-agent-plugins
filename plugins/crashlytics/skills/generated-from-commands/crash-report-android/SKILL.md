---
name: crashlytics-crash-report-android
description: Analyze Android Crashlytics logs with mandatory git blame analysis and code-level fixes. Multi-agent architecture: classifier-android → firebase-fetcher → forensics-android → validate-report. Use when the user invokes /crash-report-android.
version: 0.1.0
---

> Converted from Claude Code command `/crash-report-android`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Android Crash Analysis - Multi-Agent Edition

Analyze crash errors from Firebase Crashlytics using specialized agents.

## Configuration

**Before starting**, check if a config file exists at `.claude/crashlytics.local.md`.
If it exists, read and use these settings:
- `language` — output language for body content (default: English). Section headers stay English.
- `default_branch` — local branch name; analysis runs on `origin/<default_branch>` (default: master)
- `forensics_model` — model for forensics agent (default: opus)
- `output_format` — both / detailed_only / jira_only (default: both)
- `firebase_project_id` — pre-configured project ID (skip auto-detection if set)
- `firebase_app_id_android` — pre-configured app ID (skip auto-detection if set)

If config doesn't exist, **auto-create it with defaults** and continue:

```yaml
Bash: mkdir -p .claude && cat <<'EOF' > .claude/crashlytics.local.md
---
language: en
default_branch: master   # local branch name; plugin uses origin/<this> for git blame
default_platform: android
forensics_model: opus
output_format: both
firebase_project_id: ""
firebase_app_id_android: ""
firebase_app_id_ios: ""
---

# Crashlytics Plugin Config

Auto-created with defaults. Run `/crash-config` to customize.
EOF
```

## Multi-Agent Architecture

```
classifier(Haiku) → fetcher(Haiku) → forensics(Opus) → validate-report.py → output
```

## Workflow

### Prerequisites Check (cached)

Skip if `.claude/crashlytics-prereqs-ok` exists. Otherwise run and cache on success.

```yaml
Bash: test -f .claude/crashlytics-prereqs-ok && echo "CACHED_OK"

If not cached:
  Bash: plugins/crashlytics/scripts/check-prerequisites.sh
  Parse: OK → pass, MISSING → show fix instruction
  If ALL OK → Bash: touch .claude/crashlytics-prereqs-ok
  If any MISSING → show checklist, degrade gracefully (do NOT cache)
```

Fix instructions: node → `brew install node`, firebase → `npm install -g firebase-tools`, firebase-auth → `firebase login` in terminal, python3 → `brew install python3`.

### STEP 0: Firebase Data

**NEVER** use `mcp__plugin_crashlytics_firebase__firebase_login` — broken.

#### Path A: direct MCP fast-path (preferred)

If `firebase_project_id` and `firebase_app_id_android` are set in config AND `mcp__plugin_crashlytics_firebase__*` tools are available:

```yaml
1. Call: mcp__plugin_crashlytics_firebase__crashlytics_get_issue
     appId: {firebase_app_id_android}
     issueId: {ISSUE_ID}
2. Call: mcp__plugin_crashlytics_firebase__crashlytics_batch_get_events
     appId: {firebase_app_id_android}
     names: [sampleEvent from step 1]
```

Skip Path B if both calls succeed.

#### Path B: firebase-fetcher agent (discovery / fallback)

```yaml
Task(
  subagent_type="firebase-fetcher",
  model="haiku",
  prompt="Fetch crash data:
    Issue ID: {ISSUE_ID}
    Platform: android
    Config project_id: {firebase_project_id or ''}
    Config app_id: {firebase_app_id_android or ''}"
)
```

Parse result: extract issue data, events, stack traces, console_url.
If fallback → ask user for stack trace manually with Console URL link.

### STEP 1: Get data

**If user provided a Firebase Issue ID** — first try loading via firebase-fetcher (Step 0). Only ask for stack trace if auto-loading failed.

**If no Issue ID** — ask to provide:
- **Stack trace** (required)
- **Context**: crash count, % users, device, app version

### STEP 2: Call crash-classifier-android

```yaml
Task(
  subagent_type="crash-classifier-android",
  model="haiku",
  prompt="Classify this Android crash:
    Stack trace: {stack_trace}
    Context: Events={event_count}, Users={user_count}%, Version={app_version}, Device={device}"
)
```

### STEP 3: Call crash-forensics-android

Use `forensics_model` from config (default: opus).

```yaml
Task(
  subagent_type="crash-forensics-android",
  model="{forensics_model}",
  prompt="Analyze this Android crash with git blame:
    Classification: {classifier_output}
    Firebase data: {firebase_output}
    Stack trace: {stack_trace}
    console_url: {console_url}
    branch_ref: origin/{default_branch from config, default master}"
)
```

### STEP 3.5: Quality Gate

Pass the full forensics output through a tmp file — `echo "..."` mangles markdown with backticks/`$`/code fences.

```yaml
1. Write tool: /tmp/crashlytics-forensics-{ISSUE_ID}.md
   contents: <full forensics_output verbatim, no truncation>

2. Bash: python3 plugins/crashlytics/scripts/validate-report.py \
           --console-url "{console_url}" \
           < /tmp/crashlytics-forensics-{ISSUE_ID}.md
```

Parse the YAML result:
- `pass: true` → output report as-is.
- `pass: false`:
    - Если все элементы `missing[]` относятся к одной секции — fill in those fields using the existing forensics output.
    - Если score >= 8/14 и language config != en — высоко вероятен false-positive validator'а на переведённых заголовках. Проверить вручную каждое поле из `missing[]` по факту наличия в полном отчёте; если все на месте, считать pass: true и вывести.
    - Иначе — fill missing fields from previous steps. Do NOT re-call forensics. Do NOT re-validate against an abbreviated summary — это даёт false 1/14.
- `pass: null` (has `needs_review` items) → evaluate those fields yourself and decide pass/fail.

### STEP 4: Output results

**Format 1: Detailed Analysis** — basic info, stack trace analysis, git blame, root cause, fix (before/after), assignee, context.

**Format 2: JIRA Brief** — name, key stack trace lines, root cause, code fix, component, assignee, reproduction steps.

Output based on `output_format` from config (default: both).

## Fallback mode (if agents unavailable)

Perform analysis directly: classify → Glob/Grep files → git blame → assignee → fix → output both formats.

## Pre-submit checklist

- [ ] Classification completed (component, trigger)
- [ ] Files found via Glob/Grep or reason explained
- [ ] git blame executed on configured branch
- [ ] Assignee determined with source (git blame line X)
- [ ] Report formats match config (both by default)
- [ ] Reviewer passed or missing fields filled in
- [ ] console_url included in JIRA Brief

```yaml
Git blame + code search = MANDATORY
"TBD" = "I analyzed and ownership is unclear", NOT "I didn't check"
```
