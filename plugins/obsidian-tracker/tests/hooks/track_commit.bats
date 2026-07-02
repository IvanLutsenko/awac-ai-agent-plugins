#!/usr/bin/env bats
# Tests for hooks/track-commit.sh (PostToolUse:Bash — git commit tracking)

load helpers

setup() { setup_tracking_dir; }
teardown() { teardown_tracking_dir; }

@test "no tracking file → empty JSON" {
  rm -f "$TRACKING_FILE"
  result=$(tool_input_bash "$TEST_DIR" "git commit -m test" "[main abc1234] test" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]
}

@test "non-git command → skip" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "ls -la" "file1 file2" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  count=$(jq '.actions | length' "$TRACKING_FILE")
  [ "$count" -eq 0 ]
}

@test "npm command → skip" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "npm install" "added 100 packages" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  count=$(jq '.actions | length' "$TRACKING_FILE")
  [ "$count" -eq 0 ]
}

@test "git status → skip (not a commit)" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "git status" "On branch main" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  count=$(jq '.actions | length' "$TRACKING_FILE")
  [ "$count" -eq 0 ]
}

@test "git commit → extracts hash, adds action and linkedCommits" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "git commit -m \"fix bug\"" "[main abc1234] fix bug" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  action=$(jq -r '.actions[0]' "$TRACKING_FILE")
  [[ "$action" == *"💾 commit abc1234"* ]]

  commit=$(jq -r '.linkedCommits[0]' "$TRACKING_FILE")
  [ "$commit" = "abc1234" ]
}

@test "git -c ... commit → also detected" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "git -c user.name='Test' commit -m 'test'" "[main def5678] test" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  commit=$(jq -r '.linkedCommits[0]' "$TRACKING_FILE")
  [ "$commit" = "def5678" ]
}

@test "long hash → truncated to 7 chars" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "git commit -m 'test'" "[main abcdef1234567890abcdef1234567890abcdef12] test" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  commit=$(jq -r '.linkedCommits[0]' "$TRACKING_FILE")
  [ "${#commit}" -eq 7 ]
}

@test "no hash in output → skip" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "git commit -m 'test'" "nothing to commit, working tree clean" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  count=$(jq '.actions | length' "$TRACKING_FILE")
  [ "$count" -eq 0 ]
}

@test "duplicate commits are deduplicated in linkedCommits" {
  create_tracking_file
  tool_input_bash "$TEST_DIR" "git commit -m 'first'" "[main abc1234] first" | "$HOOKS_DIR/track-commit.sh" >/dev/null
  tool_input_bash "$TEST_DIR" "git commit -m 'second'" "[main abc1234] second" | "$HOOKS_DIR/track-commit.sh" >/dev/null

  commit_count=$(jq '.linkedCommits | length' "$TRACKING_FILE")
  [ "$commit_count" -eq 1 ]
}

@test "compound command (cd x && git commit) → tracked" {
  create_tracking_file
  tool_input_bash "$TEST_DIR" "cd /some/path && git commit -m 'fix'" "[main abc1234] fix" | "$HOOKS_DIR/track-commit.sh" >/dev/null

  commit=$(jq -r '.linkedCommits[0]' "$TRACKING_FILE")
  [ "$commit" = "abc1234" ]
}

@test "git -C path commit → tracked" {
  create_tracking_file
  tool_input_bash "$TEST_DIR" "git -C /repo commit -m 'fix'" "[main abc1234] fix" | "$HOOKS_DIR/track-commit.sh" >/dev/null

  commit=$(jq -r '.linkedCommits[0]' "$TRACKING_FILE")
  [ "$commit" = "abc1234" ]
}

@test "git -c key=val commit → tracked" {
  create_tracking_file
  tool_input_bash "$TEST_DIR" "git -c user.name=x commit -m 'fix'" "[main abc1234] fix" | "$HOOKS_DIR/track-commit.sh" >/dev/null

  commit=$(jq -r '.linkedCommits[0]' "$TRACKING_FILE")
  [ "$commit" = "abc1234" ]
}

@test "git log | grep commit → skip (not a commit)" {
  create_tracking_file
  result=$(tool_input_bash "$TEST_DIR" "git log --oneline | grep commit" "abc1234 some commit" | "$HOOKS_DIR/track-commit.sh")
  [ "$result" = "{}" ]

  count=$(jq '.actions | length' "$TRACKING_FILE")
  [ "$count" -eq 0 ]
}
