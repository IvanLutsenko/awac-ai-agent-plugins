---
name: obsidian-tracker-session-log
description: Log current session to Obsidian project. Use when the user invokes /session-log.
version: 0.1.0
---

> Converted from Claude Code command `/session-log`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Session Log Command

Logs the current Claude Code session to the specified project.

## Step 0: Check Configuration

Вызови MCP tool:
```
mcp__plugin_obsidian_tracker_obsidian__getConfig
```

**Если `initialized: false`:** выполни инициализацию как в `/projects` команде.

## Arguments

- `project-name` (optional) - Project to log session to

## Logic

1. **Resolve project:**

   Если project-name не указан:
   ```
   mcp__plugin_obsidian_tracker_obsidian__listProjects
   ```
   Покажи нумерованный список:
   | # | Project | Status |
   |---|---------|--------|
   | 1 | name    | Active |

   Пользователь может ввести номер или имя проекта.

2. **Collect session info:**

   **Сначала проверь `.claude/obsidian-tracking.json`:**
   - Если файл существует — используй данные из него (project, goal, actions)
   - Если goal пустой — сгенерируй из контекста разговора
   - Добавь недостающие actions из контекста

   **Если файла нет:**
   - Goal: Summarize main topic from conversation
   - Actions: List key tool calls and operations

   **Всегда спрашивай:**
   - Results: What was achieved
   - Next steps: Ask user via AskUserQuestion

3. **Create session via MCP:**
   ```
   mcp__plugin_obsidian_tracker_obsidian__addSession
   с параметрами:
     project = project name
     goal = session goal
     actions = ["action1", "action2", ...]
     results = what was achieved
     nextSteps = next steps
   ```

4. **Output:**
   ```
   📝 Session logged to "{project}"
   📁 Path: {path}

   Summary:
   - Goal: {goal}
   - Actions: {count} recorded
   - Next: {nextSteps}
   ```

5. **Cleanup tracking:**
   Удали `.claude/obsidian-tracking.json` после успешного логирования.
