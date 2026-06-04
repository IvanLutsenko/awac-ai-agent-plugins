---
name: obsidian-tracker-project-archive
description: Archive, restore, or permanently delete a project. Use when the user invokes /project-archive.
version: 0.1.0
---

> Converted from Claude Code command `/project-archive`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

Manage project lifecycle: archive, restore, or permanently delete projects.

## Input: $ARGUMENTS

Parse action and project name from arguments. If action is not provided, ask the user which action they want: archive, restore, or delete.

## Actions

### archive
1. Call `listProjects` (without includeArchived) to show active projects
2. If project name not provided, ask user to choose
3. Confirm with user before archiving
4. Call `archiveProject` with the project name
5. Report result

### restore
1. Call `listProjects` with `includeArchived: true`
2. Show only archived projects (where `archived: true`)
3. If no archived projects, inform user and stop
4. If project name not provided, ask user to choose
5. Call `restoreProject` with the project name
6. Report result

### delete
1. Call `listProjects` with `includeArchived: true`
2. Show archived projects first (preferred deletion targets)
3. If project name not provided, ask user to choose
4. **Always confirm with explicit warning**: this action is irreversible, all data will be lost
5. Call `deleteProject` with the project name and appropriate `fromArchive` flag
6. Report result
