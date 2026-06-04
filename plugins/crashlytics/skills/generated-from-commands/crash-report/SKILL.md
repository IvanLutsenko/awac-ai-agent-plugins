---
name: crashlytics-crash-report
description: Analyze crash from Firebase Crashlytics. Auto-detects platform from config. Usage: /crash-report <issue_id | console_url | crash info>. Use when the user invokes /crash-report.
version: 0.1.0
---

> Converted from Claude Code command `/crash-report`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Crash Analysis

Unified crash analysis command. Reads `default_platform` from config and calls the right agents.

## Step 0: Config + Platform

```yaml
1. Check config:
   Glob: .claude/crashlytics.local.md

2. If config exists → Read it, parse YAML frontmatter.
   Set PLATFORM = default_platform (android | ios)

3. If config NOT found → auto-create with defaults:
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

   Set PLATFORM = android
   Inform user: "Config created at `.claude/crashlytics.local.md` (defaults: android, origin/master, opus). Run `/crash-config` to customize."
```

Config values used throughout:
- `PLATFORM` → which agents to call + console URL format
- `default_branch` → local branch name; analysis runs on `origin/<default_branch>`
- `forensics_model` → model for forensics agent (default: opus)
- `output_format` → both / detailed_only / jira_only
- `firebase_project_id`, `firebase_app_id_{PLATFORM}` → skip auto-detect if set

## Step 0.5: Prerequisites Check (cached)

Skip if `.claude/crashlytics-prereqs-ok` exists. Otherwise run and cache on success.

```yaml
Bash: test -f .claude/crashlytics-prereqs-ok && echo "CACHED_OK"

If not cached:
  Bash: plugins/crashlytics/scripts/check-prerequisites.sh
  Parse output: OK → pass, MISSING → fail with fix instruction
  If ALL OK → Bash: touch .claude/crashlytics-prereqs-ok
  If any MISSING → show checklist, degrade gracefully (do NOT cache)
```

Fix instructions: node → `brew install node`, firebase → `npm install -g firebase-tools`, firebase-auth → `firebase login` in terminal, python3 → `brew install python3`.

## Step 1: Parse input

| Input | How to detect | Action |
|-------|---------------|--------|
| Firebase Issue ID | 32-char hex string | Use as ISSUE_ID |
| Console URL | Contains `console.firebase.google.com` | Extract project_id, app_id, issue_id from URL |
| Stack trace / text | Multi-line or descriptive | Use as crash context, skip Firebase auto-load |
| Nothing | No argument | Ask user to provide crash info |

## Step 2: Fetch Firebase Data

Two paths — pick the cheaper one available.

### Path A: direct MCP fast-path (preferred)

If `firebase_project_id` and `firebase_app_id_{PLATFORM}` are set in config AND `mcp__plugin_crashlytics_firebase__*` tools are available in this session:

```yaml
1. Call: mcp__plugin_crashlytics_firebase__crashlytics_get_issue
     appId: {firebase_app_id_{PLATFORM}}
     issueId: {ISSUE_ID}
   → captures issue metadata + sampleEvent resource name

2. Call: mcp__plugin_crashlytics_firebase__crashlytics_batch_get_events
     appId: {firebase_app_id_{PLATFORM}}
     names: [sampleEvent from step 1]
   → captures full event payload (stack, device, OS, version, blameFrame)
```

Skip Path B if both calls succeed.

### Path B: firebase-fetcher agent (fallback / discovery needed)

Use when project_id/app_id are unknown or MCP errors out:

```yaml
Task(
  subagent_type="firebase-fetcher",
  model="haiku",
  prompt="Fetch crash data:
    Issue ID: {ISSUE_ID}
    Platform: {PLATFORM}
    Config project_id: {firebase_project_id or ''}
    Config app_id: {firebase_app_id_{PLATFORM} or ''}"
)
```

Parse result: extract issue data, events, stack traces, console_url, or fallback mode.

If fallback → generate Console URL (if project_id/app_id known) and ask user for stack trace manually.

## Step 3: Classify + Forensics

```yaml
# Classifier:
Task(
  subagent_type="crash-classifier-{PLATFORM}",
  model="haiku",
  prompt="Classify this crash:
    Stack trace: {stack_trace}
    Context: Events={event_count}, Users={user_count}%, Version={app_version}, Device={device}"
)

# Forensics:
Task(
  subagent_type="crash-forensics-{PLATFORM}",
  model="{forensics_model from config, default opus}",
  prompt="Analyze this crash with git blame:
    Classification: {classifier_output}
    Firebase data: {firebase_output}
    Stack trace: {stack_trace}
    console_url: {console_url}
    branch_ref: origin/{default_branch from config, default master}"
)
```

## Step 4: Quality Gate

Forensics output is multi-page markdown with backticks, `$`, code fences and quotes — passing it through `echo "..."` mangles it. **Always go through a tmp file** so the validator gets the raw bytes.

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
    - Если все элементы `missing[]` относятся к одной секции (basic / stack / jira) — fill in those fields using the existing forensics output.
    - Если score >= 8/14 и language config != en — высоко вероятен false-positive validator'а на переведённых заголовках. Проверить вручную каждое поле из `missing[]` по факту наличия в полном отчёте; если все на месте, считать pass: true и вывести.
    - Иначе — fill missing fields from previous steps. Do NOT re-call forensics. Do NOT re-validate against an abbreviated summary — это даёт false 1/14.
- `pass: null` (has `needs_review` items) → evaluate those fields yourself and decide pass/fail.

## Step 5: Output

Based on `output_format` from config:
- `both` (default): Detailed Analysis + JIRA Brief
- `detailed_only`: Only Detailed Analysis
- `jira_only`: Only JIRA Brief

## Pre-submit checklist

- [ ] Classification completed (component, trigger)
- [ ] Files found via Glob/Grep or reason explained
- [ ] git blame executed on configured branch
- [ ] Assignee determined with source (git blame line X)
- [ ] Report formats match config
- [ ] Reviewer passed or missing fields filled in
- [ ] console_url included in JIRA Brief
