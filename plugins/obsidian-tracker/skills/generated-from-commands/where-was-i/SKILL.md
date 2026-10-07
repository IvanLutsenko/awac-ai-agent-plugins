---
name: obsidian-tracker-where-was-i
description: Show resume context: last session summary, active tasks, open bugs, decisions. Use when the user invokes /where-was-i.
version: 0.1.0
---

> Converted from Claude Code command `/where-was-i`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.
> Helper scripts ship in this skill's own `scripts/` directory. Replace
> `<this skill directory>` with the path Codex reported when it loaded this skill —
> a bare relative path would resolve against the repository under review instead.

# /where-was-i — Resume Context

## Goal
Show the user a compact context block to quickly resume work on a project.

## Steps

1. **Determine project:**
   - If `.claude/obsidian-tracking.json` exists, use the project from it.
   - Otherwise, call `findProjectByLocalPath` with the current working directory.
   - If still no project, call `listProjects` and ask the user which project.

2. **Get resume context:**
   - Call `getResumeContext` with the resolved project name.

3. **Format output** as a compact block:

```
# Resume Context for {project}

## Current Focus
{suggestedAction}

## Last Session ({date})
Completed:
- {items}

Blockers: {items or "None"}

## Active Work
Tasks:
- [{status}] {title}

Bugs:
- [{priority}] {title}

## Recent Decisions
- {DEC-id}: {title}
```

4. **Keep it token-efficient:**
   - No descriptions, only titles and statuses.
   - Target ~300-500 tokens max.
   - If a section is empty, show "None" on one line, don't skip the section.

5. **If no data exists** (no summaries, no tasks, no bugs):
   - Say "No previous session data found for {project}. This looks like a fresh start."

6. **Auto-start tracking:**
   If `.claude/obsidian-tracking.json` does not exist, start tracking for the resolved project:
   ```bash
   <this skill directory>/scripts/start-tracking.sh "{project}"
   ```

## Codex differences

- A non-interactive run (`codex exec`, CI) has nobody to answer a prompt: continue on defaults, honour whatever the invoking prompt already specified, and report which defaults were used. If the whole point of the command is to ask, say that it needs an interactive session and stop rather than inventing answers.
