---
name: obsidian-tracker-pulse
description: Cross-project status overview and analytics. Use when the user invokes /pulse.
version: 0.1.0
---

> Converted from Claude Code command `/pulse`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Pulse Command

Aggregated status across all tracked projects.

## Step 0: Check Configuration

Вызови `mcp__plugin_obsidian_tracker_obsidian__getConfig`.
Если `initialized: false` — выполни инициализацию как в `/projects`.

## Logic

1. Вызови `listProjects`.

2. Для каждого проекта вызови `listTasks`.

3. Выведи сводную таблицу:
   ```
   | Project | Backlog | In Progress | Review | Done | Bugs |
   |---------|---------|-------------|--------|------|------|
   | api     | 3       | 1           | 0      | 5    | 2    |
   | auth    | 1       | 0           | 1      | 3    | 0    |
   | **Total** | **4** | **1**       | **1**  | **8** | **2** |
   ```

4. **Highlights** (если есть):
   - Проекты с задачами в Review (готовы к завершению)
   - Проекты с > 0 багов
   - Активная tracking-сессия (из `.claude/obsidian-tracking.json`)

5. **Velocity** (если есть Done-задачи):
   ```
   Done this week: {N} tasks across {M} projects
   ```
