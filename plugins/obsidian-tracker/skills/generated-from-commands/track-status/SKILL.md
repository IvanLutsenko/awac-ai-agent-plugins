---
name: obsidian-tracker-track-status
description: Show current tracking status. Use when the user invokes /track-status.
version: 0.1.0
---

> Converted from Claude Code command `/track-status`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Track Status Command

Показывает текущий статус трекинга.

## Step 1: Check tracking

```bash
cat .claude/obsidian-tracking.json 2>/dev/null || echo "NO_TRACKING"
```

**Если NO_TRACKING:**
```
🔴 Трекинг не активен

Используй /track-start [project] чтобы начать.
```

**Если файл существует:**

Прочитай JSON и выведи:

```
🟢 Трекинг активен

- Проект: {project}
- Цель: {goal}
- Начат: {started}
- Продолжительность: {now - started}
- Actions записано: {actions.length}

Actions:
{actions.map(a => "  - " + a).join("\n")}

Команды:
- /track-stop — сохранить и завершить
- /clear — автоматически сохранит и завершит
```
