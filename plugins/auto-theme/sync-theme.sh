#!/bin/bash
# Sync editor themes with macOS system appearance (dark/light mode).
# Targets two ecosystems from one script (runs from either a Claude Code or a
# Codex hook — keeps both in sync regardless of which fired):
#   - Claude Code: ~/.claude/settings.json "theme" (+ ~/.claude.json mirror)
#   - Codex:       ~/.codex/config.toml [tui] theme
#
# Claude Code theme resolution order:
#   1. Explicit PAIR below (light<->dark), if the current theme is one of its
#      members. Lets light and dark be unrelated themes (gruvbox-light / sunset).
#   2. custom paired themes named custom:<family>-light <-> custom:<family>-dark
#   3. built-in light/dark, including -ansi / -daltonized suffixes
# Codex uses a fixed light/dark pair (its themes are global, not per-family).
# Bundled custom themes are installed on first run (copy if absent).

ROOT="${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}}"

# Detect macOS appearance: dark mode sets AppleInterfaceStyle=Dark, light = unset.
if defaults read -g AppleInterfaceStyle &>/dev/null; then
  MODE="dark"
else
  MODE="light"
fi

# Install bundled themes (copy if absent — never overwrites user-edited files;
# ponytail: delete a theme in the dest to re-pull the bundled version).
install_themes() {
  local src="$1" dst="$2" pat="$3"
  [[ -d "$src" ]] || return 0
  mkdir -p "$dst"
  for f in "$src"/$pat; do
    [[ -e "$f" ]] || continue
    [[ -e "$dst/$(basename "$f")" ]] || cp "$f" "$dst/"
  done
}
install_themes "$ROOT/themes" "$HOME/.claude/themes" "*.json"
install_themes "$ROOT/codex-themes" "$HOME/.codex/themes" "*.tmTheme"

# --- Claude Code: settings.json (authoritative) + claude.json mirror ---
python3 - "$MODE" "$HOME/.claude/settings.json" "$HOME/.claude.json" <<'PY' 2>/dev/null
import json, os, sys

mode, *paths = sys.argv[1], *sys.argv[2:]

# Explicit light<->dark pairing. {} disables it (pure family-swap).
PAIR = {"light": "custom:gruvbox-light", "dark": "custom:sunset-drive"}

def read_theme(p):
    try:
        with open(p) as f:
            return json.load(f).get("theme") or ""
    except Exception:
        return ""

# settings.json wins; fall back to claude.json for the current value.
current = read_theme(paths[0]) or read_theme(paths[1])

def target_for(cur):
    if cur in PAIR.values():
        return PAIR[mode]
    if cur.startswith("custom:") and cur.endswith(("-light", "-dark")):
        return f"{cur.rsplit('-', 1)[0]}-{mode}"
    for suffix in ("-ansi", "-daltonized"):
        if cur.endswith(suffix):
            return mode + suffix
    return mode

target = target_for(current)

for p in paths:
    if not os.path.exists(p):
        continue
    try:
        with open(p) as f:
            d = json.load(f)
    except Exception:
        continue
    if d.get("theme") == target:
        continue
    d["theme"] = target
    pretty = p.endswith("settings.json")
    with open(p, "w") as f:
        if pretty:
            json.dump(d, f, indent=2)
        else:
            json.dump(d, f, separators=(",", ":"))
PY

# --- Codex: ~/.codex/config.toml [tui] theme ---
python3 - "$MODE" "$HOME/.codex/config.toml" <<'PY' 2>/dev/null
import os, sys

mode, toml_path = sys.argv[1], sys.argv[2]
# Codex pair: light reuses Codex's built-in gruvbox-light; dark uses the
# bundled sunset-drive.tmTheme installed into ~/.codex/themes/.
TARGET = {"light": "gruvbox-light", "dark": "sunset-drive"}[mode]

if not os.path.exists(toml_path):
    sys.exit(0)

with open(toml_path) as f:
    lines = f.readlines()

# tomllib (3.11+) has no writer, so edit the [tui] theme line by hand.
out, in_tui, done = [], False, False
for line in lines:
    s = line.strip()
    if s.startswith("[") and s.endswith("]"):
        if in_tui and not done:                 # leaving [tui] without a theme key
            out.append(f'theme = "{TARGET}"\n')
            done = True
        in_tui = (s == "[tui]")
        out.append(line)
        continue
    if in_tui and not done and s.split("=", 1)[0].strip() == "theme" and "=" in s:
        out.append(f'theme = "{TARGET}"\n')
        done = True
        continue
    out.append(line)

if in_tui and not done:                          # file ended inside [tui]
    out.append(f'theme = "{TARGET}"\n')
    done = True
if not done:                                     # no [tui] table at all
    if out and not out[-1].endswith("\n"):
        out.append("\n")
    out += ["[tui]\n", f'theme = "{TARGET}"\n']

content = "".join(out)
with open(toml_path) as f:
    if f.read() == content:                      # idempotent
        sys.exit(0)
with open(toml_path, "w") as f:
    f.write(content)
PY

exit 0
