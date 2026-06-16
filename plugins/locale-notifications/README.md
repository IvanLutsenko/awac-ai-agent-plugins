# Locale Notifications

macOS notifications for Claude Code in your system language.

## Installation

```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install locale-notifications
```

> **Claude Code only.** This plugin hooks Claude Code's notification events and
> is excluded from the Codex target (`codex_exclude`) — there is no
> `codex plugin add` for it.

## How It Works

1. Detects system locale via `defaults read -g AppleLocale`
2. Auto-translates "Claude needs attention" to your language via Google Translate
3. Caches the translation locally (`~/.cache/locale-notifications/`) — only one API call ever
4. Displays a native macOS notification via `osascript`

Any language supported — no hardcoded translation list.

## Custom Message

To set a custom notification message (any language, any text), create `.claude/locale-notifications.local.md`:

```yaml
message: Your custom message here
```

The custom message takes priority over auto-translation.

## Cache

Translations are cached at `~/.cache/locale-notifications/{lang}.txt`.

To reset (e.g., after changing system locale):
```bash
rm -rf ~/.cache/locale-notifications
```

## Requirements

- macOS (uses `osascript` and `defaults`)
- `python3` (pre-installed on macOS)
- Internet connection (first notification only, then cached)

## Version

2.0.0

## Changelog

### 2.0.0
- Auto-translation via Google Translate API — any language supported
- Local caching — one API call, then works offline
- Custom message support via `.claude/locale-notifications.local.md`
- External script (`notify.sh`) instead of inline command

### 1.0.0
- Initial release with 4 hardcoded languages (en/ru/uk/kk)

## License

MIT
