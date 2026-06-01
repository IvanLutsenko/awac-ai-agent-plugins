---
name: plugin-cross-port-install-hook
description: Install the plugin-cross-port pre-commit hook into any git repository. Use when the user invokes /install-hook.
version: 0.1.0
---

> Converted from Claude Code command `/install-hook`.
> Review and adapt: remove `allowed-tools` references and any `${CLAUDE_PLUGIN_ROOT}` paths.

# Install Hook

Installs the bidirectional plugin-cross-port pre-commit hook into a target git repository.

## Arguments

- `/path/to/target-repo` (optional) — defaults to current working directory

## Steps

### Step 1 — Resolve target repo

Use the argument if provided, otherwise use cwd.

Verify it's a git repo:
```bash
git -C <target> rev-parse --show-toplevel
```
If this fails: stop with "Not a git repository: <target>".

### Step 2 — Get scripts path

Run to get the absolute path to the converter scripts:
```bash
echo "${CLAUDE_PLUGIN_ROOT}/scripts"
```

Store the result as `SCRIPTS_DIR`. This is the path that will be embedded in the generated hook.

### Step 3 — Check for existing pre-commit hook

```bash
ls <target>/.githooks/pre-commit 2>/dev/null
```

If it exists: show the user the first 5 lines and ask:
> "`.githooks/pre-commit` already exists in target repo. Overwrite?"

If they say no: stop.

### Step 4 — Create .githooks dir

```bash
mkdir -p <target>/.githooks
```

### Step 5 — Write hook

Write `<target>/.githooks/pre-commit` using the Write tool. Replace `__SCRIPTS_DIR__` with the value from Step 2.

Hook content (substitute `__SCRIPTS_DIR__` literally):

```
#!/bin/bash
# plugin-cross-port pre-commit hook
# Installed by /cross-port:install-hook — re-run after plugin updates
#
# CC-exclusive changes  (commands/, .claude-plugin/) → CC→Codex
# Codex-exclusive changes (.codex-plugin/)           → Codex→CC
# Both sides changed                                 → source_of_truth as tiebreaker
# Only shared files (skills/, README, etc.)          → no conversion

CC_TO_CODEX="__SCRIPTS_DIR__/convert_cc_to_codex.py"
CODEX_TO_CC="__SCRIPTS_DIR__/convert_codex_to_cc.py"

if [ ! -f "$CC_TO_CODEX" ] || [ ! -f "$CODEX_TO_CC" ]; then
  echo "⚠️  plugin-cross-port: scripts not found at $CC_TO_CODEX"
  echo "   Re-install the hook: /cross-port:install-hook"
  exit 0
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
CHANGED_PLUGINS=$(git diff --cached --name-only | grep '^plugins/' | cut -d/ -f1,2 | sort -u)
if [ -z "$CHANGED_PLUGINS" ]; then
  exit 0
fi

get_source_of_truth() {
  local plugin="$1"
  local decision_file="$REPO_ROOT/$plugin/.plugin-cross-port.yaml"
  local sot=""
  if [ -f "$decision_file" ]; then
    sot=$(grep '^source_of_truth:' "$decision_file" | awk '{print $2}' | tr -d "'\"")
  fi
  if [ -z "$sot" ]; then
    local has_cc="$REPO_ROOT/$plugin/.claude-plugin/plugin.json"
    local has_codex="$REPO_ROOT/$plugin/.codex-plugin/plugin.json"
    if [ -f "$has_cc" ] && [ ! -f "$has_codex" ]; then sot="claude-code"
    elif [ -f "$has_codex" ] && [ ! -f "$has_cc" ]; then sot="codex"
    else sot="claude-code"; fi
  fi
  echo "$sot"
}

run_cc_to_codex() {
  local plugin="$1"
  echo "plugin-cross-port: CC→Codex syncing $plugin"
  python3 "$CC_TO_CODEX" "$plugin" --repo-root "$REPO_ROOT" --force || { echo "❌ CC→Codex failed for $plugin. Commit aborted."; exit 1; }
  git add "$REPO_ROOT/$plugin/.codex-plugin/" "$REPO_ROOT/$plugin/skills/generated-from-commands/" "$REPO_ROOT/$plugin/.plugin-cross-port.yaml" "$REPO_ROOT/.agents/plugins/marketplace.json" 2>/dev/null || true
}

run_codex_to_cc() {
  local plugin="$1"
  echo "plugin-cross-port: Codex→CC syncing $plugin"
  python3 "$CODEX_TO_CC" "$plugin" --repo-root "$REPO_ROOT" --force || { echo "❌ Codex→CC failed for $plugin. Commit aborted."; exit 1; }
  git add "$REPO_ROOT/$plugin/.claude-plugin/" "$REPO_ROOT/$plugin/commands/generated-from-codex-"*.md "$REPO_ROOT/$plugin/.plugin-cross-port.yaml" 2>/dev/null || true
}

SYNCED=0
for PLUGIN in $CHANGED_PLUGINS; do
  STAGED=$(git diff --cached --name-only | grep "^$PLUGIN/")
  CC_CHANGED=$(echo "$STAGED" | grep -E "^$PLUGIN/(commands/[^/]+\.md|\.claude-plugin/)" | grep -v "generated-from-codex")
  CODEX_CHANGED=$(echo "$STAGED" | grep "^$PLUGIN/\.codex-plugin/")

  if [ -n "$CC_CHANGED" ] && [ -n "$CODEX_CHANGED" ]; then
    SOT=$(get_source_of_truth "$PLUGIN")
    echo "⚠️  plugin-cross-port: both sides staged in $PLUGIN — using source_of_truth=$SOT"
    [ "$SOT" = "codex" ] && run_codex_to_cc "$PLUGIN" || run_cc_to_codex "$PLUGIN"
    SYNCED=$((SYNCED + 1))
  elif [ -n "$CC_CHANGED" ]; then
    run_cc_to_codex "$PLUGIN"; SYNCED=$((SYNCED + 1))
  elif [ -n "$CODEX_CHANGED" ]; then
    run_codex_to_cc "$PLUGIN"; SYNCED=$((SYNCED + 1))
  fi
done

[ $SYNCED -gt 0 ] && echo "✅ plugin-cross-port: $SYNCED plugin(s) synced"
exit 0
```

### Step 6 — Make executable

```bash
chmod +x <target>/.githooks/pre-commit
```

### Step 7 — Configure git hooks path

Check if already set:
```bash
git -C <target> config core.hooksPath
```

If not `.githooks`: set it:
```bash
git -C <target> config core.hooksPath .githooks
```

If already set to something else: warn the user — don't overwrite, they need to merge manually.

### Step 8 — Summary

Print:
```
✅ Hook installed: <target>/.githooks/pre-commit
✅ git config core.hooksPath = .githooks

Scripts path: <SCRIPTS_DIR>

Note: if you update plugin-cross-port, re-run /cross-port:install-hook
      to refresh the scripts path in the hook.

Verify:
  git -C <target> config core.hooksPath   # → .githooks
  ls <target>/.githooks/pre-commit
```
