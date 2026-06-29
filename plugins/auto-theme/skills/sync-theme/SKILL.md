---
name: auto-theme-sync
description: Manually sync the editor theme to the current macOS appearance (light/dark). Use when the user switched macOS appearance and wants Claude Code and/or Codex themes refreshed now, or asks to fix/resync the theme. Light → gruvbox-light, dark → sunset-drive.
version: 0.1.0
---

# Auto Theme — manual sync

This plugin keeps editor themes in step with the macOS system appearance
(light/dark). Switching is normally automatic via a `UserPromptSubmit` hook;
this skill is the on-demand trigger.

Run the bundled script. It detects the macOS appearance and sets both editors:

- Claude Code — `~/.claude/settings.json` `theme` (light → `custom:gruvbox-light`, dark → `custom:sunset-drive`)
- Codex — `~/.codex/config.toml` `[tui] theme` (light → `gruvbox-light`, dark → `sunset-drive`)

It also installs the bundled themes on first run (`~/.claude/themes/`,
`~/.codex/themes/`) if absent.

```bash
bash "${CODEX_PLUGIN_ROOT}/sync-theme.sh"
```

## Automatic switching (one-time setup)

Codex plugins cannot declare hooks in their manifest, so register the hook once
in `~/.codex/hooks.json` (then trust it via `~/.codex/config.toml [hooks.state]`):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash '<plugin-root>/sync-theme.sh'", "timeout": 10 } ] }
    ]
  }
}
```
