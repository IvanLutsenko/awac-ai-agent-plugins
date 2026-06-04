---
name: crashlytics-install-permissions
description: Add Crashlytics plugin's read-only commands to your settings.json allowlist (no more permission prompts during /crash-report). Use when the user invokes /install-permissions.
version: 0.1.0
---

> Converted from Claude Code command `/install-permissions`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Install Crashlytics permissions

Adds the Crashlytics plugin's read-only Bash and MCP tools to your settings.json
allowlist so `/crashlytics:crash-report` runs without permission prompts.

**What gets added** — strictly read-only operations:
- git: `status`, `log`, `blame`, `diff`, `show`, `fetch`, `branch`, `remote`, `ls-tree`, `ls-files`, `rev-parse`, `merge-base`
- crashlytics scripts (validate-report.py, fetch-crash-data.py, check-prerequisites.sh)
- MCP read tools: `crashlytics_get_*`, `crashlytics_list_*`, `crashlytics_batch_get_events`, `crashlytics_get_report`, `firebase_get_*`, `firebase_list_*`

**What is NEVER added** — write/auth/destructive operations:
- `git push`, `git commit`, `git reset`, `git rebase`, `git clean`
- `crashlytics_update_issue`, `crashlytics_create_note`, `crashlytics_delete_note`
- `firebase_login`, `firebase_logout`, `firestore_*`, `auth_*`, `storage_*`, `messaging_*`, `realtimedatabase_*`, `remoteconfig_*`

## Step 1: Choose scope

```yaml
AskUserQuestion:
  questions:
    - question: "Where to install the allowlist?"
      header: "Scope"
      options:
        - label: "User-level (~/.claude/settings.json)"
          description: "Applies in every project. Recommended if you use the plugin in multiple repos."
        - label: "Project-level (.claude/settings.local.json)"
          description: "Only this project. Safer if you don't want global allowance."
      multiSelect: false
```

If User-level → SETTINGS_PATH = `~/.claude/settings.json`.
If Project-level → SETTINGS_PATH = `.claude/settings.local.json` (mkdir -p `.claude` if missing).

## Step 2: Read current settings

```yaml
Bash: test -f {SETTINGS_PATH} && echo EXISTS || echo NEW
Read tool: {SETTINGS_PATH}   # if EXISTS

If NEW:
  CURRENT = { "permissions": { "allow": [] } }
Else:
  CURRENT = <parsed JSON>
  Ensure permissions.allow exists, default to []
```

## Step 3: Compute the diff

```python
SAFE_SET = [
    # git read-only
    "Bash(git status:*)",
    "Bash(git log:*)",
    "Bash(git blame:*)",
    "Bash(git diff:*)",
    "Bash(git show:*)",
    "Bash(git fetch:*)",
    "Bash(git ls-tree:*)",
    "Bash(git ls-files:*)",
    "Bash(git rev-parse:*)",
    "Bash(git merge-base:*)",
    "Bash(git branch:*)",
    "Bash(git remote:*)",
    "Bash(git config --get:*)",

    # crashlytics scripts
    "Bash(plugins/crashlytics/scripts/check-prerequisites.sh:*)",
    "Bash(python3 plugins/crashlytics/scripts/validate-report.py:*)",
    "Bash(python3 plugins/crashlytics/scripts/fetch-crash-data.py:*)",

    # generic safe utils used by the plugin
    "Bash(test -f:*)",
    "Bash(touch .claude/crashlytics-prereqs-ok)",

    # MCP — read-only Crashlytics
    "mcp__plugin_crashlytics_firebase__crashlytics_get_issue",
    "mcp__plugin_crashlytics_firebase__crashlytics_batch_get_events",
    "mcp__plugin_crashlytics_firebase__crashlytics_list_events",
    "mcp__plugin_crashlytics_firebase__crashlytics_get_report",
    "mcp__plugin_crashlytics_firebase__crashlytics_list_notes",

    # MCP — read-only Firebase project info
    "mcp__plugin_crashlytics_firebase__firebase_get_environment",
    "mcp__plugin_crashlytics_firebase__firebase_list_apps",
    "mcp__plugin_crashlytics_firebase__firebase_get_project",
    "mcp__plugin_crashlytics_firebase__firebase_list_projects",
    "mcp__plugin_crashlytics_firebase__firebase_get_sdk_config",
]

EXISTING = set(CURRENT["permissions"]["allow"])
TO_ADD   = [r for r in SAFE_SET if r not in EXISTING]
```

If `TO_ADD` is empty → inform user "All Crashlytics permissions already present in {SETTINGS_PATH}." and exit.

## Step 4: Show diff and confirm

Print:

```
Adding {N} new rule(s) to {SETTINGS_PATH}:
  + Bash(git fetch:*)
  + Bash(git ls-tree:*)
  + ...
```

Then:

```yaml
AskUserQuestion:
  questions:
    - question: "Apply these changes to {SETTINGS_PATH}?"
      header: "Confirm"
      options:
        - label: "Yes, write the file"
          description: "Append the new rules to permissions.allow"
        - label: "Cancel"
          description: "Don't change anything"
      multiSelect: false
```

If Cancel → exit without writes.

## Step 5: Write merged settings

```yaml
NEW = CURRENT
NEW["permissions"]["allow"] = sorted(set(EXISTING) | set(SAFE_SET))

Write tool: {SETTINGS_PATH}
  contents: json.dumps(NEW, indent=2, ensure_ascii=False) + "\n"
```

For project-level path — `mkdir -p .claude` first if needed.

## Step 6: Confirm

Display:

```
Crashlytics allowlist installed.

  Scope: {scope}
  File:  {SETTINGS_PATH}
  Added: {N} rule(s)

Restart your current Claude Code session for permissions to take effect.
Run /crashlytics:crash-report again — no permission prompts on read-only steps.
```

## Notes

- The script never adds write/auth/destructive rules.
- The script never modifies `permissions.deny` or other settings sections.
- Existing rules are preserved (set-union merge, sorted output).
- Re-run anytime — duplicate rules are deduplicated.

## Long-term TODO

When Claude Code adds a `permissions` field to `plugin.json` for declarative
allowlists, this command becomes obsolete. Track Anthropic's plugin spec.
