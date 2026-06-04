---
name: obsidian-tracker-project-new
description: Create a new project in Obsidian. Use when the user invokes /project-new.
version: 0.1.0
---

> Converted from Claude Code command `/project-new`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Project New Command

Creates a new project structure in Obsidian.

## Step 0: Check Configuration

Вызови MCP tool:
```
mcp__plugin_obsidian_tracker_obsidian__getConfig
```

**Если `initialized: false`:** выполни инициализацию как в `/projects` команде.

## Logic

1. **Collect project info via AskUserQuestion:**
   - Project name (ОБЯЗАТЕЛЬНО)
   - Description (ОБЯЗАТЕЛЬНО)

2. **Detect subproject intent:**
   Если пользователь упоминает "подпроект", "в проекте X", "sub" — это подпроект.
   Вызови `listProjects`, найди родительский проект и передай его имя в `parent`.

3. **Create project via MCP:**
   ```
   mcp__plugin_obsidian_tracker_obsidian__createProject
   с параметрами:
     name = project name
     description = description
     parent = parent project name (если подпроект)
   ```

4. **Output:**
   ```
   Project "{name}" created
   Path: {path}

   Quick commands:
   - `/projects {name}` - view details
   - `/project-bug {name}` - add bug
   - `/session-log {name}` - log session
   ```

5. **Auto-start tracking:**
   ```bash
   plugins/obsidian-tracker/scripts/start-tracking.sh "{name}"
   ```
