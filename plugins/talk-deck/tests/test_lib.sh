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

# Remote URLs -> web base, and the blob link of a file in a repo.
check "gitlab ssh remote" "$(td_remote_web git@gitlab.example.kz:group/sub/repo.git)" "https://gitlab.example.kz/group/sub/repo"
check "ssh:// remote with a port" "$(td_remote_web ssh://git@gitlab.example.kz:2222/group/repo.git)" "https://gitlab.example.kz/group/repo"
check "https remote with a user" "$(td_remote_web https://user@github.com/owner/repo.git)" "https://github.com/owner/repo"
check "https remote without .git" "$(td_remote_web https://github.com/owner/repo/)" "https://github.com/owner/repo"
td_remote_web /local/path >/dev/null; check "a local path is not a web remote" "$?" "1"
repo="$tmp/repo"; mkdir -p "$repo/docs/deck"
git -C "$repo" init -q -b main && git -C "$repo" remote add origin git@gitlab.example.kz:group/repo.git
touch "$repo/docs/deck/talk.pdf"
check "gitlab blob link on the current branch" "$(td_blob_link "$repo/docs/deck/talk.pdf")" "https://gitlab.example.kz/group/repo/-/blob/main/docs/deck/talk.pdf"
git -C "$repo" remote set-url origin https://github.com/owner/repo.git
# A remote default branch other than the local one: origin/HEAD -> origin/trunk.
git -C "$repo" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/trunk
check "github blob link on the remote default branch" "$(td_blob_link "$repo/docs/deck/talk.pdf")" "https://github.com/owner/repo/blob/trunk/docs/deck/talk.pdf"
td_blob_link "$HOME/.claude/talk-deck.local.md" >/dev/null; check "a file outside a repo has no link" "$?" "1"

# frames.sh: names from the deck map, one PNG per PDF page, with stand-ins for Craft and poppler.
printf 'import json\nprint(json.dumps([{"page":1,"key":"cover"},{"page":2,"key":"Why Now"}]))\n' > "$craft/scripts/deck_map.py"
cat > "$craft/scripts/lib.py" <<'PY'
def chromium_args(width, height):
    code = "import sys; [open(a.split('=', 1)[1], 'w').write('pdf') for a in sys.argv if a.startswith('--print-to-pdf=')]"
    return ["python3", "-c", code]
PY
mkdir -p "$tmp/bin"
printf '#!/bin/bash\nfor i in 01 02; do : > "${@: -1}-$i.png"; done\n' > "$tmp/bin/pdftoppm"; chmod +x "$tmp/bin/pdftoppm"
printf -- '---\nauthor: x\n---\n' > "$HOME/.claude/talk-deck.local.md"
out="$(PATH="$tmp/bin:$PATH" CRAFT_HOME="$craft" CHROMIUM=/bin/true bash "$root/scripts/frames.sh" "$HOME/site/res/talk" "$tmp/frames" 2>&1)"
check "frames.sh names files by page and key" "$(ls "$tmp/frames" | tr '\n' ' ')" "01-cover.png 02-why-now.png "
check "frames.sh reports the count" "$(grep '^count=' <<<"$out")" "count=2"
printf '#!/bin/bash\n: > "${@: -1}-1.png"\n' > "$tmp/bin/pdftoppm"
err="$(PATH="$tmp/bin:$PATH" CRAFT_HOME="$craft" CHROMIUM=/bin/true bash "$root/scripts/frames.sh" "$HOME/site/res/talk" "$tmp/frames2" 2>&1 >/dev/null)"
check "frames.sh fails when pages and map differ" "$(grep -o 'the PDF has 1 pages, the deck map 2' <<<"$err")" "the PDF has 1 pages, the deck map 2"

exit $fail
