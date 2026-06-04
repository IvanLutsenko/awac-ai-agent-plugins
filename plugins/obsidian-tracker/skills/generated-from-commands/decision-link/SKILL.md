---
name: obsidian-tracker-decision-link
description: Link commits, PRs, tasks, or bugs to a decision. Use when the user invokes /decision-link.
version: 0.1.0
---

> Converted from Claude Code command `/decision-link`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# /decision-link — Link Entity to Decision

## Steps

1. **Determine project** from tracking file or `findProjectByLocalPath`.

2. **Resolve decision ID:**
   - If argument provided, use it.
   - Otherwise, list decisions and ask.

3. **Ask what to link** via `AskUserQuestion`:
   - Commits (git hashes, short 7-char format)
   - PRs (#number or owner/repo#number)
   - Tasks (TASK-N)
   - Sessions (session IDs)

4. **Link** via `linkEntity` with entity="DEC-{id}" and the collected links.

5. **Confirm** the updated links.

Note: `linkEntity` works for any entity type (TASK, BUG, DEC). This command is a convenience wrapper focused on decisions.
