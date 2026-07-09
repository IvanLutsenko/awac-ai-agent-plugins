#!/bin/bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PLUGIN_DIR="$ROOT_DIR/plugins/locale-notifications"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin" "$TMP_DIR/project/.claude"

cat > "$TMP_DIR/project/.claude/locale-notifications.local.md" <<'EOF'
message: He said "check this"
EOF

cat > "$TMP_DIR/bin/osascript" <<'EOF'
#!/bin/bash
printf '%s\n' "$@" > "$TEST_OSASCRIPT_ARGS"
EOF
chmod +x "$TMP_DIR/bin/osascript"

cat > "$TMP_DIR/bin/defaults" <<'EOF'
#!/bin/bash
echo en_US
EOF
chmod +x "$TMP_DIR/bin/defaults"

cat > "$TMP_DIR/bin/curl" <<'EOF'
#!/bin/bash
echo '[]'
EOF
chmod +x "$TMP_DIR/bin/curl"

TEST_OSASCRIPT_ARGS="$TMP_DIR/osascript-args.txt" \
PATH="$TMP_DIR/bin:$PATH" \
HOME="$TMP_DIR/home" \
bash "$PLUGIN_DIR/notify.sh" <<< "{\"cwd\":\"$TMP_DIR/project\"}"

args=()
while IFS= read -r line; do
  args+=("$line")
done < "$TMP_DIR/osascript-args.txt"

[[ "${#args[@]}" -eq 8 ]] || {
  printf 'expected 8 osascript args, got %s\n' "${#args[@]}" >&2
  printf '%s\n' "${args[@]}" >&2
  exit 1
}

[[ "${args[0]}" == "-e" ]]
[[ "${args[1]}" == "on run argv" ]]
[[ "${args[2]}" == "-e" ]]
[[ "${args[3]}" == 'display notification (item 1 of argv) with title "Claude Code"' ]]
[[ "${args[4]}" == "-e" ]]
[[ "${args[5]}" == "end run" ]]
[[ "${args[6]}" == "--" ]]
[[ "${args[7]}" == 'He said "check this"' ]]

echo "ok"
