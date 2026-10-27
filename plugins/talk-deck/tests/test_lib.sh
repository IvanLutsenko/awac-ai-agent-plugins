#!/usr/bin/env bash
# Checks for talk-deck's lib.sh and the edit hook. Run: bash tests/test_lib.sh
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail=0
check() { if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1: expected '$3', got '$2'"; fail=1; fi; }

export HOME="$tmp/home"; mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/talk-deck.local.md" <<'CFG'
---
author: "Test Author"
contact: https://example.com/a:b
site_repo: ~/site
---
body: ignored
CFG
mkdir -p "$HOME/site/res/talk/media" "$HOME/site/res/plain"
touch "$HOME/site/res/talk/index.html" "$HOME/site/res/talk/deck-theme.css" "$HOME/site/res/plain/index.html"
source "$root/scripts/lib.sh"
cd "$tmp"

check "quoted value" "$(td_author)" "Test Author"
check "colon inside a value" "$(td_contact)" "https://example.com/a:b"
check "default language" "$(td_lang)" "ru"
check "decks dir from site repo" "$(td_decks_dir)" "$HOME/site/res"
check "deck of a nested file" "$(td_deck_of "$HOME/site/res/talk/media/x.png" 2>/dev/null || echo none)" "$HOME/site/res/talk"
td_deck_of "$HOME/site/res/plain/index.html" >/dev/null; check "folder without a theme is not a deck" "$?" "1"
check "deck by slug" "$(td_resolve_deck talk)" "$HOME/site/res/talk"
td_resolve_deck plain >/dev/null; check "slug that is not a deck fails" "$?" "1"
td_resolve_deck nope >/dev/null; check "unknown slug fails" "$?" "1"
td_resolve_deck >/dev/null; check "current folder outside a deck fails" "$?" "1"

# A stand-in Craft whose static check fails, so the hook's verdict is visible.
craft="$tmp/craft"; mkdir -p "$craft/scripts"; touch "$craft/scripts/scaffold.py"
printf 'import sys\nprint("Error: broken local asset")\nsys.exit(1)\n' > "$craft/scripts/check_project.py"
edit() { printf '{"tool_input":{"file_path":"%s"}}' "$1" | CRAFT_HOME="$2" bash "$root/scripts/check-on-edit.sh" 2>"$tmp/err"; }

edit "$HOME/site/res/talk/index.html" "$craft"
check "hook blocks a deck that fails the check" "$?" "2"
grep -q "broken local asset" "$tmp/err"; check "hook passes the check output on" "$?" "0"
edit "/etc/hosts" "$craft"
check "hook ignores files outside decks" "$?" "0"
mv "$craft/scripts/scaffold.py" "$tmp/away.py"
edit "$HOME/site/res/talk/index.html" "$tmp/none"
check "hook reports a missing Craft" "$?" "1"
grep -q "not checked" "$tmp/err"; check "missing Craft says the deck is unchecked" "$?" "0"
mv "$tmp/away.py" "$craft/scripts/scaffold.py"
printf 'not json' | bash "$root/scripts/check-on-edit.sh" 2>"$tmp/err"
check "hook reports unreadable input" "$?" "1"
grep -q "could not read" "$tmp/err"; check "unreadable input has a message" "$?" "0"

CRAFT_HOME="$craft" CHROMIUM=/bin/true td_require talk 2>/dev/null
check "td_require sets the deck" "$deck" "$HOME/site/res/talk"
check "td_require sets Craft" "$craft" "$tmp/craft"
CRAFT_HOME="$craft" CHROMIUM=/bin/true td_require nope 2>/dev/null; check "td_require fails off a deck" "$?" "1"
printf -- '---\ncraft_home: ~/missing\n---\n' > "$HOME/.claude/talk-deck.local.md"
td_craft_home >/dev/null 2>&1; check "a wrong craft_home is an error" "$?" "1"

exit $fail
