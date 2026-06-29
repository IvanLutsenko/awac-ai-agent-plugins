# auto-theme

Keeps your editor theme in step with the macOS system appearance (light/dark).
Targets **Claude Code** and **Codex** from one script, and ships custom
`gruvbox-light` / `sunset-drive` themes that it installs on first run.

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install auto-theme
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add auto-theme@awac-ai-agent-plugins
```

## What it does

On every prompt (`UserPromptSubmit` hook) it reads the macOS appearance
(`defaults read -g AppleInterfaceStyle`) and sets the matching theme:

- **light** → Claude Code `custom:gruvbox-light`, Codex `[tui] theme = "gruvbox-light"`
- **dark** → Claude Code `custom:sunset-drive`, Codex `[tui] theme = "sunset-drive"`

- **Claude Code** — writes `theme` to `~/.claude/settings.json` (the authoritative
  location in the current CLI) and mirrors it to `~/.claude.json`.
- **Codex** — writes `[tui] theme` to `~/.codex/config.toml`.
- Idempotent: no file write when the theme already matches.
- Bundled themes are installed on first run (copy-if-absent) into
  `~/.claude/themes/` (`.json`) and `~/.codex/themes/` (`.tmTheme`); editing a
  destination file is preserved — delete it to re-pull the bundled version.

## Theme resolution (Claude Code)

1. Explicit pair — `light → custom:gruvbox-light`, `dark → custom:sunset-drive`.
2. Otherwise a `custom:<family>-light ↔ custom:<family>-dark` swap.
3. Otherwise the built-in `light` / `dark` (keeping `-ansi` / `-daltonized`).

Edit the `PAIR` dict at the top of `sync-theme.sh` to change the pairing
(`PAIR = {}` falls back to pure family-swap).

## Codex: enabling the hook

Codex plugins cannot declare hooks in their manifest, so register the hook once
in `~/.codex/hooks.json`, then trust it (`~/.codex/config.toml` `[hooks.state]`):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash '<plugin-root>/sync-theme.sh'", "timeout": 10 } ] }
    ]
  }
}
```

On Codex, `[tui] theme` controls **syntax-highlighting** themes; `sunset-drive`
is shipped as a `.tmTheme`, `gruvbox-light` is built in. The `auto-theme-sync`
skill runs the same sync on demand.

## Notes

- macOS only (relies on `AppleInterfaceStyle`).
- Warp and Ghostty already sync natively — leave them to their own settings.
