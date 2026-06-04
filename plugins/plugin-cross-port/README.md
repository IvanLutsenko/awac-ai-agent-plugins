# plugin-cross-port

Bridge between Claude Code and Codex plugin formats.

Converts individual plugins in either direction and reconciles dual-target
Claude Code and Codex marketplaces. A repository chooses one canonical
marketplace, while each plugin keeps its own `source_of_truth`.

**Version:** 0.7.0

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

# CLI wrapper without marketplace side effects
python3 plugins/plugin-cross-port/scripts/cross_port.py \
  plugin convert plugins/obsidian-tracker --from claude-code --to codex
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

.agents/plugins/marketplace.json         <- Codex marketplace entry added in standalone script mode
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

# CLI wrapper without marketplace side effects
python3 plugins/plugin-cross-port/scripts/cross_port.py \
  plugin convert plugins/my-codex-plugin --from codex --to claude-code
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

## Marketplace reconciliation

Attach a repository marketplace once, then use deterministic full-list sync:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py \
  marketplace attach --source claude-code

python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace sync
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace check

python3 plugins/plugin-cross-port/scripts/cross_port.py \
  plugin attach plugins/example --source codex

python3 plugins/plugin-cross-port/scripts/cross_port.py \
  plugin switch-source plugins/example --to claude-code
```

`marketplace attach` records repository-level state in
`.plugin-cross-port.marketplace.yaml`. The selected marketplace owns root
metadata, active plugin ordering, and deletion. Each plugin state file owns its
own `source_of_truth`, so mixed repositories are supported.

If a canonical marketplace entry is removed, `marketplace sync` removes the
entire `plugins/<name>/` directory after validating that the path is local,
inside `plugins_dir`, and has a basename matching the plugin name. Use Git to
recover deleted plugin files.

Failed or review-required Codex targets are published with
`policy.installation: "NOT_AVAILABLE"`. Failed Claude Code targets are omitted
from the Claude Code marketplace because there is no confirmed disabled field.

The pre-commit hook delegates to `marketplace sync --changed-only ... --stage`
and rejects staged edits on generated sides according to plugin-level state.

See `references/continuous-mode.md` for GitHub Actions and pre-commit hook examples.

---

## Semantic adaptation

`0.7.0` adds an explicit review workflow for behavior that cannot be
mechanically derived:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin adapt plugins/example
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin adapt plugins/example --apply
```

`plugin adapt` writes:

- `plugins/example/.plugin-cross-port/adaptation-plan.md`
- `plugins/example/.plugin-cross-port/adaptation-state.yaml`

The analyze command does not modify target files. `--apply` applies the whole
reviewed plan atomically and rejects stale source snapshots. During
`marketplace sync`, reproducible adaptation rules are replayed. Stale critical
semantic adaptations set plugin status to `needs-review`; Codex marketplace
entries become `NOT_AVAILABLE`. Stale non-critical adaptations keep the target
available and emit a warning.

---

## Limitations

- **Hooks** — `SessionStart`, `PostToolUse`, etc. have no Codex equivalent. Implement as GitHub Actions if needed.
- **Agents** — not auto-converted; requires manual review and placement in `skills/`.
- **`${CLAUDE_PLUGIN_ROOT}`** — CC-specific path variable; **auto-rewritten** to the plugin's repo-relative path (`plugins/<name>`) in generated skills.
- **`allowed-tools`** — CC per-command tool allowlist has no Codex analog; **auto-dropped** from generated skill frontmatter.
- **MCP tool names** — same `.mcp.json` format, but verify tool IDs work in target environment.
- **Semantic adaptation** — hooks and ecosystem-specific paths still require
  review through `plugin adapt`; sync never invents new semantic behavior.

---

## Reference

- `references/mapping.md` — CC -> Codex field mapping table
- `references/decision-file.md` — `.plugin-cross-port.yaml` schema
- `references/continuous-mode.md` — CI and pre-commit examples

---

## Changelog

### 0.7.0
- Add `plugin adapt` and `plugin adapt --apply`
- Write adaptation plan and adaptation state under `.plugin-cross-port/`
- Reject stale source snapshots before applying reviewed plans
- Replay reproducible adaptation rules during sync
- Mark stale critical semantic adaptations as needs-review

### 0.6.0
- Add marketplace attach, sync and check workflows
- Support mixed Claude Code-first and Codex-first plugins
- Reconcile ordered marketplace entries and preserve non-derived policy fields
- Mark unavailable Codex targets with NOT_AVAILABLE and omit broken CC targets
- Remove plugin directories when canonical marketplace entries are removed
- Replace hook direction guessing with declared source-of-truth enforcement

### 0.5.0
- Remove stale converter-owned commands and skills when source files disappear
- Honor plugin-relative `manually_maintained` paths in both conversion directions
- Preserve manually maintained generated files during cleanup

### 0.4.0
- Repo-level config `.plugin-cross-port.config.yaml`: `plugins_dir`, `codex_marketplace`, `default_source_of_truth`
- Config read by both Python scripts and pre-commit hook

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
