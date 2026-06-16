---
name: Convert Claude Code Plugin to Codex
description: One-shot conversion of a Claude Code plugin to Codex format. Use when asked to convert, port, or add Codex support for a plugin in this repository.
version: 0.1.0
---

# Convert Claude Code Plugin → Codex

Convert a single plugin from Claude Code format to Codex-compatible format.

## When to activate

- User says "convert X to Codex", "port X to Codex", "add Codex support for X"
- User provides a path like `plugins/obsidian-tracker` or just a plugin name

## Inputs

- **Plugin path** — relative to repo root, e.g. `plugins/obsidian-tracker`
- **Repo root** — directory containing `.claude-plugin/marketplace.json` (default: detect from cwd)

## Workflow

## Phase 0: Vendor external plugins

When the plugin lives outside this repository, copy it into `plugins_dir`
before conversion. Review license and attribution, resolve name collisions,
discard stale foreign generated artifacts after review, and explicitly choose
the source of truth when attaching. Deterministic scripts never copy files
between repositories.

### Step 1 — Read source

Read the following files from the target plugin (skip if absent):

1. `<plugin-path>/.claude-plugin/plugin.json` — required
2. `<plugin-path>/.mcp.json` — optional
3. `<plugin-path>/skills/` directory listing — optional
4. `<plugin-path>/commands/` directory listing — optional
5. `<plugin-path>/agents/` directory listing — optional
6. `<plugin-path>/README.md` — optional

If `.claude-plugin/plugin.json` is missing, stop and report: "Not a Claude Code plugin: no .claude-plugin/plugin.json found."

### Step 2 — Check for existing Codex manifest

If `<plugin-path>/.codex-plugin/plugin.json` already exists, read it and note what's already generated. Ask the user:
> "`.codex-plugin/plugin.json` already exists. Overwrite or merge?"

### Step 3 — Generate `.codex-plugin/plugin.json`

Build the Codex manifest from the source Claude manifest:

```json
{
  "name": "<same as CC name>",
  "version": "<same version>",
  "description": "<same description>",
  "author": {
    "name": "<author.name from CC>"
  },
  "skills": "./skills/",
  "interface": {
    "displayName": "<Title Case of plugin name>",
    "shortDescription": "<first sentence of description, max 80 chars>",
    "developerName": "<author.name>",
    "category": "Development",
    "capabilities": ["Read", "Write"]
  }
}
```

Rules:
- Do NOT include `hooks` — Codex validator rejects it
- Do NOT include `commands` array — Codex uses skills only
- Do NOT include `agents` array — not supported in Codex manifest
- `skills` points to `./skills/` (the shared directory at plugin root)

### Step 4 — Copy/verify `skills/`

If the plugin has an existing `skills/` directory, it is shared between Claude Code and Codex. No action needed — just confirm it exists.

### Step 5 — Convert `commands/` to Codex skills

For each `.md` file in `<plugin-path>/commands/`:

1. Read the file and extract frontmatter (`description`, `argument-hint`)
2. Create directory: `<plugin-path>/skills/generated-from-commands/<command-name>/`
3. Write `SKILL.md`:

```markdown
---
name: <plugin-name>-<command-name>
description: <description from command frontmatter, or "Command: <command-name>" if absent>. Use when the user invokes /<command-name>.
version: 0.1.0
---

> Converted from Claude Code command `/<command-name>`.
> Review and adapt: remove CC-specific allowed-tools frontmatter, MCP tool references that may not exist in Codex.

<original command body — everything after frontmatter>
```

Skip files already in `skills/generated-from-commands/` if they are newer than the source command (idempotent).

### Step 6 — Convert `agents/` to Codex skills

Codex has no separate agents concept, so each agent becomes a standalone skill.
For each `.md` file in `<plugin-path>/agents/`:

1. Read the file and extract frontmatter (`name`, `description`)
2. Clean the description: CC agents pack `<example>` trigger blocks into a
   quoted single-line description with literal `\n` escapes. Keep only the text
   before `Examples:` and unescape it.
3. Create directory: `<plugin-path>/skills/generated-from-agents/<agent-name>/`
4. Write `SKILL.md`:

```markdown
---
name: <plugin-name>-<agent-name>
description: <cleaned description, already trigger-shaped>
version: 0.1.0
---

> Converted from Claude Code agent `<agent-name>`.
> Codex has no separate agents concept; this runs as a standalone skill.

<original agent system prompt — everything after frontmatter, ${CLAUDE_PLUGIN_ROOT} rewritten>
```

Skip files already in `skills/generated-from-agents/` if they are newer than the source agent (idempotent).

**Orchestration is not rewritten.** A command that spawned these agents via the Task tool keeps referencing them by name — they now resolve as skills. Inlining a full multi-agent workflow into one skill is per-plugin manual work.

For hooks in `plugin.json`:
- **WARNING**: Hooks (`SessionStart`, `PostToolUse`, etc.) have no Codex equivalent. Review and implement as skill side-effects or GitHub Actions if needed.

### Step 7 — Create `.plugin-cross-port.yaml`

Write `<plugin-path>/.plugin-cross-port.yaml`:

Write it as JSON (the loader reads it back JSON-first; nested YAML breaks re-runs):

```json
{
  "version": 1,
  "plugin": "<plugin-name>",
  "generated_at": "<ISO date>",
  "source_of_truth": "claude-code",
  "decisions": {
    "skills_shared": true,
    "commands_converted": true,
    "agents_converted": true,
    "hooks_converted": false
  },
  "warnings": [],
  "manually_maintained": []
}
```

### Step 8 — Update Codex marketplace

For standalone one-shot conversion, the legacy converter may update the Codex
marketplace. In a managed repository, prefer:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py \
  plugin convert <plugin-path> --from claude-code --to codex
python3 plugins/plugin-cross-port/scripts/cross_port.py \
  plugin attach <plugin-path> --source claude-code
```

Read `.agents/plugins/marketplace.json` (create if absent).
Add or update entry for this plugin:

```json
{
  "name": "<plugin-name>",
  "source": {
    "source": "local",
    "path": "./plugins/<plugin-name>"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Development"
}
```

Avoid duplicates — check if an entry with the same `name` already exists.

### Step 9 — Show summary

Print a summary block:

```
Plugin Cross-Port: <plugin-name>
================================
Generated:
  ✅ .codex-plugin/plugin.json
  ✅ skills/generated-from-commands/<N> skills
  ✅ skills/generated-from-agents/<N> skills
  ✅ .plugin-cross-port.yaml
  ✅ .agents/plugins/marketplace.json updated

Shared (no action):
  📁 skills/ — <N existing skills>

Warnings:
  ⚠️  hooks — no Codex equivalent

Manual steps:
  1. Review generated skills in skills/generated-from-commands/
     Remove CC-specific allowed-tools lines and MCP tool references that differ in Codex.
  2. Review skills/generated-from-agents/ — agents run as standalone skills;
     any command that orchestrated them references them by name.
  3. Run: python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py <plugin-path> --repo-root .
     to validate idempotency.
```

## Error handling

- Missing `.claude-plugin/plugin.json` → stop with clear error
- `.codex-plugin/` dir doesn't exist → create it
- `.agents/plugins/marketplace.json` doesn't exist → create it with empty `plugins: []`
- Command file has no frontmatter → use filename as description, emit warning
