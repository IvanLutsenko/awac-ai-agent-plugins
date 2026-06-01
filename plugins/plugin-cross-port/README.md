# plugin-cross-port

Bridge between Claude Code and Codex plugin formats.

Converts a Claude Code plugin to Codex format — one-shot or continuously via CI. Source of truth is always the Claude Code side.

**Version:** 0.3.0

---

## One-shot conversion

### Via skill (interactive)

When working in Claude Code:

```
Convert plugins/obsidian-tracker to Codex
```

The `cc-to-codex` skill will analyze the plugin and generate Codex-compatible files.

### Via script (deterministic)

```bash
# Preview changes (nothing written)
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --dry-run

# Run conversion
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root .

# Force overwrite all generated files
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --force

# Strict: fail if agents/hooks are unresolved
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --strict
```

### Output

For a plugin at `plugins/obsidian-tracker` the script generates:

```
plugins/obsidian-tracker/
  .codex-plugin/
    plugin.json                          <- Codex manifest (no hooks, skills-only)
  skills/
    generated-from-commands/
      projects/SKILL.md                  <- converted from commands/projects.md
      project-new/SKILL.md
      ... (one per command)
  .plugin-cross-port.yaml                <- decision file

.agents/plugins/marketplace.json         <- Codex marketplace entry added
```

---

## Codex → Claude Code

### Via skill (interactive)

```
Convert plugins/my-codex-plugin from Codex to Claude Code
```

### Via script (deterministic)

```bash
# Preview changes
python3 plugins/plugin-cross-port/scripts/convert_codex_to_cc.py plugins/my-codex-plugin --repo-root . --dry-run

# Run conversion
python3 plugins/plugin-cross-port/scripts/convert_codex_to_cc.py plugins/my-codex-plugin --repo-root .
```

### Output

```
plugins/my-codex-plugin/
  .claude-plugin/
    plugin.json                          <- CC manifest
  commands/
    generated-from-codex-<skill>.md      <- one per Codex skill
  .plugin-cross-port.yaml                <- source_of_truth: codex
```

---

## Continuous mode

After initial conversion, re-run the script whenever commands change:

```bash
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root .
```

The script is **idempotent** — up-to-date generated files are skipped.

See `references/continuous-mode.md` for GitHub Actions and pre-commit hook examples.

---

## Limitations

- **Hooks** — `SessionStart`, `PostToolUse`, etc. have no Codex equivalent. Implement as GitHub Actions if needed.
- **Agents** — not auto-converted; requires manual review and placement in `skills/`.
- **`${CLAUDE_PLUGIN_ROOT}`** — CC-specific path variable; remove from generated skills or replace with relative paths.
- **`allowed-tools`** — CC per-command tool allowlist has no Codex analog; remove from generated skills.
- **MCP tool names** — same `.mcp.json` format, but verify tool IDs work in target environment.

---

## Reference

- `references/mapping.md` — CC -> Codex field mapping table
- `references/decision-file.md` — `.plugin-cross-port.yaml` schema
- `references/continuous-mode.md` — CI and pre-commit examples

---

## Changelog

### 0.3.0
- `/cross-port:install-hook` — install pre-commit hook into any git repo with absolute scripts path

### 0.2.0
- Added Codex → CC direction: `convert_codex_to_cc.py` script + `codex-to-cc` skill
- Capabilities → allowed-tools mapping (Read/Write/Execute/Network)
- Round-trip recovery: strips "Converted from Claude Code command" headers on reverse pass
- `source_of_truth` field in `.plugin-cross-port.yaml`

### 0.1.0
- Initial release: one-shot conversion script, cc-to-codex skill, maintain-dual-target skill
- Supports: commands -> skills, manifest conversion, Codex marketplace entry
- Limitations: agents and hooks require manual handling
