---
name: Convert Codex Plugin to Claude Code
description: One-shot conversion of a Codex plugin to Claude Code format. Use when asked to convert a Codex plugin to Claude Code, add CC support for a Codex plugin, or reverse-port a plugin from Codex.
version: 0.2.0
---

# Convert Codex Plugin → Claude Code

Convert a single plugin from Codex format to Claude Code-compatible format.

## When to activate

- User says "convert X from Codex to CC", "add Claude Code support for X", "reverse-port X"
- User provides a Codex plugin path and asks for CC compatibility
- Round-trip recovery: CC plugin was converted to Codex, now needs CC files restored

## Inputs

- **Plugin path** — relative to repo root, e.g. `plugins/my-codex-plugin`
- **Repo root** — directory containing `.agents/plugins/marketplace.json` (default: detect from cwd)

## Workflow

### Step 1 — Read source

Read the following files from the target plugin (skip if absent):

1. `<plugin-path>/.codex-plugin/plugin.json` — required
2. `<plugin-path>/skills/` directory listing — list all SKILL.md files
3. `<plugin-path>/.mcp.json` — optional
4. `<plugin-path>/README.md` — optional
5. `<plugin-path>/.plugin-cross-port.yaml` — optional (check source_of_truth)

If `.codex-plugin/plugin.json` is missing, stop and report: "Not a Codex plugin: no .codex-plugin/plugin.json found."

If `.plugin-cross-port.yaml` exists with `source_of_truth: claude-code`, warn:
> "This plugin was originally created in Claude Code. Reverse conversion may produce redundant files. Proceed?"

### Step 2 — Check for existing CC manifest

If `<plugin-path>/.claude-plugin/plugin.json` already exists, read it. Ask:
> "`.claude-plugin/plugin.json` already exists. Overwrite or merge?"

### Step 3 — Generate `.claude-plugin/plugin.json`

Build the CC manifest from the Codex manifest:

```json
{
  "name": "<same as Codex name>",
  "description": "<same description>",
  "version": "<same version>",
  "author": {
    "name": "<author.name>",
    "email": "",
    "url": ""
  },
  "keywords": ["<interface.category>", "codex", "cross-platform"],
  "license": "MIT",
  "skills": [
    "./skills/<name>/SKILL.md"
    // list all SKILL.md files from skills/
  ]
}
```

Notes:
- Do NOT generate `hooks` — must be added manually based on plugin logic
- List existing skills explicitly in `skills` array
- `commands` array is only added if Step 5 produces generated commands

### Step 4 — Verify `skills/`

`skills/` is shared between Codex and CC. List all existing skills and confirm they load correctly in CC (SKILL.md format with frontmatter: `name`, `description`).

If a skill has no frontmatter or missing `description`, emit warning.

### Step 5 — Convert `skills/` to CC commands

For each `skills/<name>/SKILL.md` (exclude `generated-from-commands/`):

1. Read SKILL.md frontmatter: `name`, `description`
2. Map `interface.capabilities` → `allowed-tools`:
   - `Read` → `Read, Glob, Grep`
   - `Write` → `Write, Edit`
   - `Execute` → `Bash`
   - `Network` → `WebFetch, WebSearch`
3. Write `<plugin-path>/commands/generated-from-codex-<skill-name>.md`:

```markdown
---
description: <description from SKILL.md, without "Use when the user invokes /X." suffix>
argument-hint: "[args]"
allowed-tools: [<mapped tools>]
---

> Converted from Codex skill `<skill-name>`.
> Review and adapt: add specific `allowed-tools` entries and `${CLAUDE_PLUGIN_ROOT}` paths as needed.

<SKILL.md body>
```

If skill body starts with `> Converted from Claude Code command` (round-trip case), strip that header.

Skip generated commands if newer than source skill (idempotent).

### Step 6 — Hooks warning

CC supports hooks (`SessionStart`, `PostToolUse`, `PreCompact`, `Stop`, etc.). Codex has no equivalent.

Emit notice:
> "Hooks are not auto-generated. If this plugin needs event-driven behavior (session tracking, auto-commit, etc.), add hooks manually to `.claude-plugin/plugin.json`."

If `--strict` and `.plugin-cross-port.yaml` doesn't have `decisions.hooks_converted: true`, fail with this message.

### Step 7 — Create/update `.plugin-cross-port.yaml`

```yaml
version: 1
plugin: <plugin-name>
generated_at: <ISO date>
source_of_truth: codex

decisions:
  skills_shared: true
  skills_converted_to_commands: true
  hooks_converted: false      # must be set manually after adding hooks

warnings: []

manually_maintained: []
```

### Step 8 — Summary

```
Plugin Cross-Port (Codex → CC): <plugin-name>
=============================================
Generated:
  ✅ .claude-plugin/plugin.json
  ✅ commands/generated-from-codex-<N> commands
  ✅ .plugin-cross-port.yaml

Shared (no action):
  skills/ — <N skills>

Notices:
  ℹ️  hooks — not generated, add manually if needed

Manual steps:
  1. Review commands/generated-from-codex-*.md — refine allowed-tools.
  2. Add hooks to .claude-plugin/plugin.json if needed.
  3. Rename/move generated commands to commands/<name>.md when satisfied.
  4. Run: python3 scripts/convert_codex_to_cc.py <plugin-path> --repo-root .
     to validate idempotency.
```

## Error handling

- Missing `.codex-plugin/plugin.json` → stop with clear error
- `skills/` is empty → warn (or strict fail)
- Skill has no frontmatter → use filename as description, emit warning
- `interface.capabilities` missing → default to `["Read", "Write"]`
