---
name: obsidian-tracker-projects
description: List all projects from Obsidian or show specific project details. Use when the user invokes /projects.
version: 0.1.0
---

> Converted from Claude Code command `/projects`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Projects Command

Lists all tracked projects from Obsidian or shows details for a specific project.

## Step 0: Check Configuration

Вызови MCP tool для проверки конфигурации:

```
mcp__plugin_obsidian_tracker_obsidian__getConfig
```

**Если `initialized: false` или `vaultPath: "NOT SET"`:**

1. Спроси путь к Obsidian vault через AskUserQuestion:
   - Опция 1: `~/Documents/Obsidian/Projects` (Recommended)
   - Опция 2: `~/Documents/GitHub/obsidian/MCP/Projects`
   - Опция 3: Другой путь

2. Вызови MCP tool для инициализации:
   ```
   mcp__plugin_obsidian_tracker_obsidian__initVault
   с параметром vaultPath = выбранный путь
   ```

3. Выведи: `✅ Obsidian Tracker инициализирован: {vault_path}`

**Если `initialized: true`:** переходи к Logic.

## Arguments

- `project-name` (optional) - Show details for specific project

## Examples

```
/projects                           # List all projects
/projects awac-claude-code-plugins  # Show specific project
```

## Logic

1. **If no argument provided:**

   Вызови:
   ```
   mcp__plugin_obsidian_tracker_obsidian__listProjects
   ```

   Выведи нумерованную таблицу с деревом. Если у проекта есть `subprojects`, покажи их с нумерацией `X.Y`.
   **Важно:** для отступов подпроектов используй обычные пробелы, НЕ `&nbsp;` — в терминале они не рендерятся.

   | # | Project | Status | Tasks | Bugs |
   |---|---------|--------|-------|------|
   | 1 | name    | Active | 5     | 2    |
   | 2 | name2   | Active | 3     | 0    |
   | 3 | parent-project | Active | 0 | 4 |
   | 3.1 |   sub-project-a | Active | 2 | 1 |
   | 3.2 |   sub-project-b | Active | 1 | 0 |

   Подсказка: `Введи номер проекта (например 3 или 3.1) или /projects <name> для деталей`

   **Если пользователь вводит число** (целое или `X.Y`) — выбери соответствующий проект/подпроект и покажи детали (как в пункте 2). Для подпроекта используй полный путь: `parent/subproject`.

2. **If project-name provided:**

   Вызови:
   ```
   mcp__plugin_obsidian_tracker_obsidian__getProject
   с параметром name = project-name
   ```

   Выведи:
   - Project description
   - Open bugs (with count)
   - Recent sessions
   - Quick commands: `/project-bug {name}`, `/session-log {name}`

   **Auto-start tracking:**
   После вывода информации о проекте, автоматически запусти трекинг:
   ```bash
   plugins/obsidian-tracker/scripts/start-tracking.sh "{project-name}"
   ```
