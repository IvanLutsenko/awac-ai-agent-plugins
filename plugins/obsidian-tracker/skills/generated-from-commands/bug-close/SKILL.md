---
name: obsidian-tracker-bug-close
description: Close a bug report in Obsidian project. Use when the user invokes /bug-close.
version: 0.1.0
---

> Converted from Claude Code command `/bug-close`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Bug Close Command

Closes a bug report in the specified project.

## Step 0: Check Configuration

Вызови MCP tool:
```
mcp__plugin_obsidian_tracker_obsidian__getConfig
```

**Если `initialized: false`:** выполни инициализацию как в `/projects` команде.

## Arguments

- `project-name` (optional) - Project containing the bug
- `--title` - Bug title (optional, will show list if not provided)

## Examples

```
/bug-close awac-claude-code-plugins
/bug-close awac-claude-code-plugins --title "Write tool фейлится"
```

## Logic

1. **Resolve project:**

   Если project-name не указан:
   ```
   mcp__plugin_obsidian_tracker_obsidian__listProjects
   ```
   Покажи нумерованный список (только проекты с багами > 0):
   | # | Project | Open Bugs |
   |---|---------|-----------|
   | 1 | name    | 3         |

   Пользователь может ввести номер или имя проекта.

2. **Select bug:**

   Получи список багов:
   ```
   mcp__plugin_obsidian_tracker_obsidian__getProject
   с параметром name = project name
   ```

   Если --title не указан, покажи только Open баги:
   | # | Bug | Priority |
   |---|-----|----------|
   | 1 | title | high   |

   Пользователь может ввести номер или название.

3. **Collect resolution (optional):**
   Спроси: "Как был решён баг? (Enter чтобы пропустить)"

4. **Close bug via MCP:**
   ```
   mcp__plugin_obsidian_tracker_obsidian__closeBug
   с параметрами:
     project = project name
     title = bug title
     resolution = resolution text (если указан)
   ```

5. **Output:**
   ```
   ✅ Bug closed: "{title}"
   📁 Path: {path}
   📅 Resolved: {date}
   ```

6. **Update tracking (если активен):**
   Если `.claude/obsidian-tracking.json` существует — прочитай, добавь в actions `Closed bug: {title}` и перезапиши через Bash.
