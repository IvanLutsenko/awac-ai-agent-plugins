---
name: obsidian-tracker-import
description: Parse a document into structured tasks. Use when the user invokes /import.
version: 0.1.0
---

> Converted from Claude Code command `/import`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Import Command

Reads a markdown/text file and intelligently extracts tasks from it.

## Arguments

- file-path (required) - Path to file to parse
- --project (required) - Target project name

## Examples

```
/import ~/notes/design-research.md --project minimap
/import ./TODO.md --project api
/import ~/brainstorm.md --project auth
```

## Logic

1. Парси аргументы. Если не хватает — спроси через AskUserQuestion.

2. Если --project не указан:
   Вызови `listProjects`, покажи список, спроси.

3. Прочитай файл через Read tool.

4. Проанализируй содержимое:
   - Ищи actionable items: bullet points, numbered lists, TODO, FIXME, чеклисты `- [ ]`
   - Для каждого определи:
     - **title** — краткое описание задачи
     - **priority** — по ключевым словам (critical/urgent → critical, important/high → high, nice-to-have/low → low, остальное → medium)
     - **effort** — по сложности описания (простое → "30m", среднее → "2h", сложное → "4h"+)

5. Покажи извлечённые задачи пользователю:
   ```
   | # | Title | Priority | Effort |
   |---|-------|----------|--------|
   | 1 | ...   | high     | 2h     |
   | 2 | ...   | medium   | 1h     |
   ```

   Спроси подтверждение: "Создать {N} задач? (да / убрать # / изменить)"

6. Для каждой подтверждённой задачи вызови:
   ```
   mcp__plugin_obsidian_tracker_obsidian__addTask
   с параметрами: project, title, priority, effort
   ```

7. Выведи итог:
   ```
   Created {N} tasks in {project}
   All added to Backlog on kanban board
   ```
