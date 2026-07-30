#!/usr/bin/env bats
# Tests for hooks/pre-compact.sh (PreCompact)
#
# Unlike the other hooks this one must NOT emit JSON: stdout goes straight into
# the compaction summarizer's customInstructions, so even "{}" would show up as
# a bogus instruction.

load helpers

setup() { setup_tracking_dir; }
teardown() { teardown_tracking_dir; }

@test "no tracking file → silence, exit 0" {
  rm -f "$TRACKING_FILE"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/pre-compact.sh")
  [ "$?" -eq 0 ]
  [ -z "$result" ]
}

@test "malformed tracking file → silence, exit 0" {
  printf 'not json{' > "$TRACKING_FILE"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/pre-compact.sh")
  [ -z "$result" ]
}

@test "tracking file exists → project, goal and action count" {
  create_tracking_file_with_actions "compact-project"
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/pre-compact.sh")
  [[ "$result" == *"OBSIDIAN TRACKING ACTIVE"* ]]
  [[ "$result" == *"Project=compact-project"* ]]
  [[ "$result" == *"Goal=test goal"* ]]
  [[ "$result" == *"Actions=1"* ]]
}

@test "output is plain text, not JSON" {
  create_tracking_file
  result=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/pre-compact.sh")
  [[ "$result" != "{"* ]]
  [[ "$result" != *"hookSpecificOutput"* ]]
}

@test "output is a single line" {
  create_tracking_file
  lines=$(hook_input "$TEST_DIR" | "$HOOKS_DIR/pre-compact.sh" | wc -l | tr -d ' ')
  [ "$lines" = "1" ]
}
