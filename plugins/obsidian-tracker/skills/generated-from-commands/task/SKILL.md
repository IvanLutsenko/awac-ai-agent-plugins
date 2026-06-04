---
name: obsidian-tracker-task
description: Create a new task in an Obsidian project with kanban board. Use when the user invokes /task.
version: 0.1.0
---

> Converted from Claude Code command `/task`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Task Command

Creates a task with auto-increment ID and adds to kanban board (Backlog column).

## Step 0: Check Configuration

Вызови `mcp__plugin_obsidian_tracker_obsidian__getConfig`.
Если `initialized: false` — выполни инициализацию как в `/projects`.

## Arguments

- title (required) - Task title (first quoted string or positional arg)
- --project (optional) - Project name
- --priority (optional) - critical|high|medium|low (default: medium)
- --effort (optional) - Time estimate (e.g., "2h", "1d", "30m")
- --assignee (optional) - Assignee name
- Любые дополнительные --key value передаются в extra (расширяемая YAML-схема)

## Examples

```
/task "Add rate limiting" --project api --priority high --effort 2h
/task "Fix login bug"
/task "Update docs" --project myapp --effort 30m --client Acme
```

## Logic

1. Парси аргументы из пользовательского ввода.

2. Если --project не указан:
   Вызови `listProjects`, покажи нумерованный список, спроси у пользователя.

3. Если title не указан:
   Спроси через AskUserQuestion.

4. **Определи тип информации:**
   - Если пользователь даёт actionable задачу (что-то нужно СДЕЛАТЬ) — это TASK, используй `addTask`.
   - Если пользователь даёт справочную информацию, контекст, описание, заявку, требования — это КОНТЕКСТ ПРОЕКТА, используй `updateProject` с параметром `context`.
   - Примеры TASK: "Подготовить презентацию", "Пофиксить баг", "Добавить фичу"
   - Примеры КОНТЕКСТ: "Вот моя заявка на конференцию: ...", "Требования от заказчика: ...", "Описание проекта: ..."
   - Если не уверен — спроси пользователя: "Это задача или контекст проекта?"

5. Собери extra-поля: все --key value кроме project/priority/effort/assignee.

6. Вызови MCP tool:
   - Для TASK: `addTask` с параметрами: project, title, priority, effort, assignee, extra
   - Для КОНТЕКСТ: `updateProject` с параметрами: project, context (форматированный markdown)

7. Выведи:
   - Для TASK:
   ```
   TASK-{id}: "{title}"
   Board: Backlog | Priority: {priority} | Effort: {effort}
   ```
   - Для КОНТЕКСТ:
   ```
   Context added to project "{project}"
   ```

8. **Auto-start tracking:**
   Если `.claude/obsidian-tracking.json` НЕ существует — запусти трекинг:
   ```bash
   plugins/obsidian-tracker/scripts/start-tracking.sh "{project}"
   ```
   Если файл уже существует — прочитай через Read, добавь `"Created TASK-{id}: {title}"` в actions, перезапиши через `Bash(cat*)`.
