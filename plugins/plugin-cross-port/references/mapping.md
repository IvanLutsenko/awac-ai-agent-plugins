# Claude Code → Codex Mapping

Deterministic conversion remains separate from semantic adaptation. The same
converter engines are used by one-shot conversion and marketplace
reconciliation.

## Manifest

| Claude Code | Codex | Notes |
|---|---|---|
| `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` | Different schemas; no hooks in Codex |
| `name`, `version`, `description` | same | Direct copy |
| `author.name` | `author.name` | Only `name` field in Codex |
| `hooks` | — | No equivalent; warn |
| `commands` array | — | Commands become skills |
| `agents` array | — | No manifest field; each agent becomes a skill |
| `mcpServers` | `.mcp.json` | Same format |

## Components

| Claude Code | Codex | Conversion |
|---|---|---|
| `.mcp.json` | `.mcp.json` | Copy as-is |
| `skills/<name>/SKILL.md` | `skills/<name>/SKILL.md` | Shared directory, no conversion needed |
| `commands/<name>.md` | `skills/generated-from-commands/<name>/SKILL.md` | Automated via script |
| `agents/<name>.md` | `skills/generated-from-agents/<name>/SKILL.md` | Automated via script; `<example>` blocks stripped from description |
| `hooks/*` | — | Manual; no Codex equivalent |

## Field mapping: CC command → Codex skill

| CC command frontmatter | Codex SKILL.md frontmatter | Notes |
|---|---|---|
| `description` | `description` | Appended with trigger hint |
| `argument-hint` | — | Not used in Codex |
| `allowed-tools` | — | Removed; Codex uses `capabilities` in manifest |
| body (markdown) | body | Preserved with "Converted from" header |

## Codex manifest fields

```json
{
  "name": "plugin-name",
  "version": "0.1.0",
  "description": "...",
  "author": { "name": "..." },
  "skills": "./skills/",
  "interface": {
    "displayName": "...",
    "shortDescription": "...",
    "developerName": "...",
    "category": "Development",
    "capabilities": ["Read", "Write"]
  }
}
```

`capabilities` allowed values: `Read`, `Write`, `Execute`, `Network`.

## Known limitations

- **Hooks**: SessionStart, PostToolUse, PreCompact, Stop, etc. have no Codex equivalent. Functionality must be reimplemented as GitHub Actions or skill side-effects.
- **Agents**: Codex has no separate `agents/` concept, so each `agents/<name>.md` is converted to a standalone skill under `skills/generated-from-agents/`. The agent's system prompt becomes the skill body and its description is reused (CC `<example>` trigger blocks stripped). What does *not* convert is orchestration: a command that spawned several agents via the Task tool keeps referencing them by name — they now resolve as skills, but inlining a true multi-agent workflow into one skill is per-plugin manual work.
- **allowed-tools**: CC's per-command tool allowlist has no Codex analog. Codex uses manifest-level `capabilities`.
- **MCP tool names**: Same `.mcp.json` format works, but tool IDs may differ between environments. Review generated skills for `mcp__*` references.
- **`${CLAUDE_PLUGIN_ROOT}`**: This CC variable is not available in Codex. The converter auto-rewrites it to the plugin's repo-relative path (`plugins/<name>`) in generated skills, matching the convention used by hand-written Codex skills.

## Marketplace Mapping

| Field | Owner |
|---|---|
| Marketplace root metadata | Canonical marketplace selected by attach |
| Plugin order and active plugin set | Canonical marketplace |
| `name`, `version`, `description`, `author` | Authoritative plugin manifest |
| Entry source path | Current local `./plugins/<name>` path |
| Existing category | Preserved; defaulted for new entries |
| Codex `policy.authentication` | Preserved; default `ON_INSTALL` |
| Codex `policy.products` | Preserved when present |
| Codex `policy.installation` | Derived from reconciliation status |

Codex failed or review-required targets are published as `NOT_AVAILABLE`.
Failed Claude Code targets are omitted from the Claude Code marketplace.

`0.7.0` implements the planned semantic adaptation workflow. It still does not
pretend that hooks or ecosystem-specific paths have direct equivalents; it
records and applies reviewed plans explicitly.
