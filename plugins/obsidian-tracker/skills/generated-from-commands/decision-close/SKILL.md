---
name: obsidian-tracker-decision-close
description: Close an active decision. Use when the user invokes /decision-close.
version: 0.1.0
---

> Converted from Claude Code command `/decision-close`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# /decision-close — Close Decision

## Steps

1. **Determine project** from tracking file or `findProjectByLocalPath`.

2. **Resolve decision ID:**
   - If argument provided (e.g., `1` or `DEC-001`), use it directly.
   - Otherwise, call `listDecisions` with status="Active" and show the list. Ask user to pick.

3. **Show the decision** via `getDecision` so the user can confirm.

4. **Ask for close reason** (optional) via `AskUserQuestion`.

5. **Close** via `closeDecision`.

6. **Confirm** closure.
