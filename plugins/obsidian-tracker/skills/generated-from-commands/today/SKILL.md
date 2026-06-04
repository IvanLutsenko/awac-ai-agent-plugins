---
name: obsidian-tracker-today
description: Show daily task dashboard across all projects. Use when the user invokes /today.
version: 0.1.0
---

> Converted from Claude Code command `/today`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Today Command

Shows what to focus on today across all tracked projects.

## Step 0: Check Configuration

Вызови `mcp__plugin_obsidian_tracker_obsidian__getConfig`.
Если `initialized: false` — выполни инициализацию как в `/projects`.

## Logic

1. Вызови `listProjects`.

2. Для каждого проекта с `tasks > 0` вызови `listTasks`.

3. Собери и выведи дашборд:

   ### In Progress
   Задачи со статусом "In Progress" из всех проектов:
   ```
   | Project | Task | Title |
   |---------|------|-------|
   | api     | TASK-3 | Rate limiting |
   ```

   ### Up Next
   Задачи в Backlog (приоритет: показывай все, но выделяй high/critical):
   ```
   | Project | Task | Title | Priority |
   ```

   ### In Review
   Задачи в Review (если есть):
   ```
   | Project | Task | Title |
   ```

4. **Tracking:**
   Если `.claude/obsidian-tracking.json` существует — покажи текущую сессию:
   ```
   Active session: {project} — {goal} (started {time ago})
   ```

5. **Summary line:**
   ```
   {X} in progress, {Y} in backlog, {Z} in review | Active bugs: {B}
   ```
