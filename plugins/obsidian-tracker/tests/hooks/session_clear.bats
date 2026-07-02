#!/usr/bin/env bats
# Tests for hooks/session-clear.sh (SessionStart:clear)
# New behavior: bash writes raw session to vault, moves tracking file

load helpers

setup() {
  setup_tracking_dir
  # Mock vault + config
  VAULT_DIR="$(mktemp -d)"
  CONFIG_DIR="$HOME/.config/obsidian-tracker"
  CONFIG_FILE="$CONFIG_DIR/config.json"
  # Backup real config if exists
  [ -f "$CONFIG_FILE" ] && cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
  mkdir -p "$CONFIG_DIR"
  echo "{\"vaultPath\":\"$VAULT_DIR\",\"initialized\":true}" > "$CONFIG_FILE"
}

teardown() {
  teardown_tracking_dir
  rm -rf "$VAULT_DIR"
  # Restore real config
  if [ -f "${CONFIG_FILE}.bak" ]; then
    mv "${CONFIG_FILE}.bak" "$CONFIG_FILE"
  else
    rm -f "$CONFIG_FILE"
  fi
}

setup_vault_project() {
  local project="${1:-test-project}"
  mkdir -p "$VAULT_DIR/$project/Sessions"
  touch "$VAULT_DIR/$project/Board.md"
}

@test "no tracking file → empty JSON" {
  rm -f "$TRACKING_FILE"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh")
  assert_valid_json "$result"
  [ "$result" = "{}" ]
}

@test "tracking file exists + vault project → returns systemMessage" {
  create_tracking_file "test-project" "fix bugs"
  setup_vault_project "test-project"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh")
  assert_valid_json "$result"
  assert_json_has "$result" '.systemMessage'
}

@test "writes session entry to vault" {
  create_tracking_file "test-project" "fix bugs"
  setup_vault_project "test-project"
  hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh" >/dev/null
  session_file=$(ls "$VAULT_DIR/test-project/Sessions/Session - "*.md 2>/dev/null | head -1)
  [ -n "$session_file" ]
  grep -q "fix bugs" "$session_file"
}

@test "session entry contains actions" {
  create_tracking_file_with_actions "test-project"
  setup_vault_project "test-project"
  hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh" >/dev/null
  session_file=$(ls "$VAULT_DIR/test-project/Sessions/Session - "*.md 2>/dev/null | head -1)
  grep -q "existing.kt" "$session_file"
}

@test "moves tracking file to obsidian-session-saved.json" {
  create_tracking_file "test-project"
  setup_vault_project "test-project"
  hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh" >/dev/null
  [ ! -f "$TRACKING_FILE" ]
  [ -f "$TRACKING_DIR/obsidian-session-saved.json" ]
}

@test "project dir not found → returns {}, tracking file stays" {
  create_tracking_file "nonexistent-project"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh")
  [ "$result" = "{}" ]
  [ -f "$TRACKING_FILE" ]
}

@test "empty project → returns {}" {
  echo '{"project":"","goal":"x","actions":[],"startedAt":"2026-01-01T00:00:00Z"}' > "$TRACKING_FILE"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh")
  [ "$result" = "{}" ]
}

@test "no hookSpecificOutput" {
  create_tracking_file "test-project"
  setup_vault_project "test-project"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh")
  has_hso=$(echo "$result" | jq 'has("hookSpecificOutput")')
  [ "$has_hso" = "false" ]
}

@test "format contract: entry structure matches mcp renderSessionEntry golden" {
  # CONTRACT: mirrors mcp/helpers.ts renderSessionEntry() (vitest golden test).
  # Section headers, their order, and the trailing --- must stay identical.
  create_tracking_file "test-project" "fix bugs"
  setup_vault_project "test-project"
  hook_input "$TEST_DIR" | "$HOOKS_DIR/session-clear.sh" >/dev/null
  session_file=$(ls "$VAULT_DIR/test-project/Sessions/Session - "*.md 2>/dev/null | head -1)

  structure=$(grep -E '^(## |### |---)' "$session_file" | head -6)
  expected='## Session - '
  echo "$structure" | head -1 | grep -qE '^## Session - [0-9]{2}:[0-9]{2} UTC \(' 
  [ "$(echo "$structure" | sed -n 2p)" = "### Goal" ]
  [ "$(echo "$structure" | sed -n 3p)" = "### Actions" ]
  [ "$(echo "$structure" | sed -n 4p)" = "### Results" ]
  [ "$(echo "$structure" | sed -n 5p)" = "### Next Time" ]
  [ "$(echo "$structure" | sed -n 6p)" = "---" ]
}
