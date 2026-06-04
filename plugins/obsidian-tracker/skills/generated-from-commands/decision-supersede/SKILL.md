---
name: obsidian-tracker-decision-supersede
description: Supersede a decision with a new one. Use when the user invokes /decision-supersede.
version: 0.1.0
---

> Converted from Claude Code command `/decision-supersede`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# /decision-supersede — Supersede Decision

## Steps

1. **Determine project** from tracking file or `findProjectByLocalPath`.

2. **Resolve old decision ID:**
   - If argument provided, use it.
   - Otherwise, list active decisions and ask.

3. **Show the old decision** for context.

4. **Collect new decision info** via `AskUserQuestion`:
   - Title, Context, Decision, Consequences for the replacement.

5. **Supersede** via `supersedeDecision`.
   - This creates the new decision and marks the old one as Superseded with a backlink.

6. **Confirm** with both old and new decision IDs.
