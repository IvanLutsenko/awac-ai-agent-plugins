---
description: Install the plugin-cross-port pre-commit hook into any git repository
argument-hint: "[/path/to/target-repo]"
allowed-tools: Bash(git*), Bash(mkdir*), Bash(chmod*), Bash(ls*), Bash(echo*), Bash(test*), Read, Write
---

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

CC_TO_CODEX="__SCRIPTS_DIR__/convert_cc_to_codex.py"
CODEX_TO_CC="__SCRIPTS_DIR__/convert_codex_to_cc.py"

if [ ! -f "$CC_TO_CODEX" ] || [ ! -f "$CODEX_TO_CC" ]; then
  echo "⚠️  plugin-cross-port: scripts not found. Re-run /cross-port:install-hook"
  exit 0
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
CONFIG_FILE="$REPO_ROOT/.plugin-cross-port.config.yaml"
PLUGINS_DIR="plugins"
CODEX_MARKETPLACE=".agents/plugins/marketplace.json"
DEFAULT_SOT="claude-code"

if [ -f "$CONFIG_FILE" ]; then
  val=$(grep '^plugins_dir:' "$CONFIG_FILE" | awk '{print $2}' | tr -d "'\"")
  [ -n "$val" ] && PLUGINS_DIR="$val"
  val=$(grep '^codex_marketplace:' "$CONFIG_FILE" | awk '{print $2}' | tr -d "'\"")
  [ -n "$val" ] && CODEX_MARKETPLACE="$val"
  val=$(grep '^default_source_of_truth:' "$CONFIG_FILE" | awk '{print $2}' | tr -d "'\"")
  [ -n "$val" ] && DEFAULT_SOT="$val"
fi

CHANGED_PLUGINS=$(git diff --cached --name-only | grep "^$PLUGINS_DIR/" | cut -d/ -f1,2 | sort -u)
if [ -z "$CHANGED_PLUGINS" ]; then exit 0; fi

get_source_of_truth() {
  local plugin="$1"; local sot=""
  local df="$REPO_ROOT/$plugin/.plugin-cross-port.json"
  [ -f "$df" ] && sot=$(grep '^source_of_truth:' "$df" | awk '{print $2}' | tr -d "'\"")
  if [ -z "$sot" ]; then
    local hc="$REPO_ROOT/$plugin/.claude-plugin/plugin.json"
    local hd="$REPO_ROOT/$plugin/.codex-plugin/plugin.json"
    if [ -f "$hc" ] && [ ! -f "$hd" ]; then sot="claude-code"
    elif [ -f "$hd" ] && [ ! -f "$hc" ]; then sot="codex"
    else sot="$DEFAULT_SOT"; fi
  fi
  echo "$sot"
}

run_cc_to_codex() {
  local plugin="$1"
  echo "plugin-cross-port: CC→Codex syncing $plugin"
  python3 "$CC_TO_CODEX" "$plugin" --repo-root "$REPO_ROOT" --force || { echo "❌ CC→Codex failed for $plugin. Commit aborted."; exit 1; }
  git add "$REPO_ROOT/$plugin/.codex-plugin/" "$REPO_ROOT/$plugin/skills/generated-from-commands/" "$REPO_ROOT/$plugin/.plugin-cross-port.json" "$REPO_ROOT/$CODEX_MARKETPLACE" 2>/dev/null || true
}

run_codex_to_cc() {
  local plugin="$1"
  echo "plugin-cross-port: Codex→CC syncing $plugin"
  python3 "$CODEX_TO_CC" "$plugin" --repo-root "$REPO_ROOT" --force || { echo "❌ Codex→CC failed for $plugin. Commit aborted."; exit 1; }
  git add "$REPO_ROOT/$plugin/.claude-plugin/" "$REPO_ROOT/$plugin/commands/generated-from-codex-"*.md "$REPO_ROOT/$plugin/.plugin-cross-port.json" 2>/dev/null || true
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
