---
name: obsidian-tracker-decision-new
description: Create a new lightweight Architecture Decision Record (ADR). Use when the user invokes /decision-new.
version: 0.1.0
---

> Converted from Claude Code command `/decision-new`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# /decision-new — Create Decision

## Steps

1. **Determine project:**
   - If `.claude/obsidian-tracking.json` exists, use the project from it.
   - Otherwise, call `findProjectByLocalPath` with cwd.
   - If still no project, ask the user.

2. **Collect decision info:**
   - If the user provided a description in the command argument, extract title/context/decision/consequences from it.
   - Otherwise ask via `AskUserQuestion`:
     - **Title** — short name for the decision
     - **Context** — what problem or situation led to this decision?
     - **Decision** — what was decided?
     - **Consequences** — what are the trade-offs?

3. **Check for related entities:**
   - If tracking is active, check if current work relates to tasks or bugs.
   - Offer to link them (optional).

4. **Create the decision:**
   - Call `addDecision` with all collected info.

5. **Update tracking:**
   - If `.claude/obsidian-tracking.json` exists, add "📋 Decision DEC-{id}: {title}" to actions.

6. **Confirm** with the decision ID and a brief summary.
