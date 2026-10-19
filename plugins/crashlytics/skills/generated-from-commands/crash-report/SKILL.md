---
name: crashlytics-crash-report
description: Analyze crash from Firebase Crashlytics. Auto-detects platform from config. Usage: /crash-report <issue_id | console_url | crash info>. Use when the user invokes /crash-report.
version: 0.1.0
---

> Converted from Claude Code command `/crash-report`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.
> Helper scripts ship in this skill's own `scripts/` directory. Replace
> `<this skill directory>` with the path Codex reported when it loaded this skill —
> a bare relative path would resolve against the repository under review instead.

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
  Bash: <this skill directory>/scripts/check-prerequisites.sh
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
    branch_ref: origin/{default_branch from config, default master}
    report_path: /tmp/crashlytics-forensics-{ISSUE_ID}.md"
)
```

## Step 4: Quality Gate

The forensics agent writes its full report to `/tmp/crashlytics-forensics-{ISSUE_ID}.md` (`report_path`). Validate **that file**. Do not write it from your own copy of the report: a retyped report comes out shortened, and the validator then checks a different text from the one the user sees.

```yaml
1. Bash: test -s /tmp/crashlytics-forensics-{ISSUE_ID}.md || echo MISSING
   MISSING (the agent skipped the step) → Write tool: the forensics output byte-for-byte
   as returned — a copy, no edits, no summary, no reformatting.

2. Bash: python3 <this skill directory>/scripts/validate-report.py \
           --console-url "{console_url}" \
           < /tmp/crashlytics-forensics-{ISSUE_ID}.md
```

Parse the YAML result:
- `pass: true` → output the report from this file.
- `pass: false` → add each field from `missing[]` to the file with Edit, using data from earlier steps (do not re-call forensics). Re-run the validator on the same file. One round only. Still `pass: false` → output the report and the line `Валидатор: <score>, не хватает: <fields>`.
- `needs_review[]` → judge each listed field yourself and give the verdict per field.

The validator verdict is final:
- Do not declare a pass after a manual check, and do not explain a fail away as a false positive.
- If you think the validator is wrong, say so separately: name the field and quote the text it missed. That is a validator bug report, not a pass.
- Validate only this file. Never run the validator on a summary, an excerpt or a reformatted copy.

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
- [ ] Validator ran on the agent's report file; its verdict is reported as-is
- [ ] console_url included in JIRA Brief
