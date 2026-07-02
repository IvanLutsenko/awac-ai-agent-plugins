# Repo-Level Config: `.plugin-cross-port.config.yaml`

Optional config file at the **repo root** (not inside a plugin directory).
If absent, all defaults apply — nothing breaks.

## Format

```yaml
plugins_dir: plugins                              # where plugins live (default: plugins)
codex_marketplace: .agents/plugins/marketplace.json  # Codex marketplace output path
cc_marketplace: .claude-plugin/marketplace.json   # Claude Code marketplace path
marketplace_state: .plugin-cross-port.marketplace.json # repository marketplace state
default_source_of_truth: claude-code              # fallback when no decision file exists
```

## Fields

**`plugins_dir`** — directory containing managed plugin directories.
Change this if your repo uses a non-standard layout (e.g., `packages`, `src`).

**`codex_marketplace`** — path to the Codex marketplace used by reconciliation
and standalone CC -> Codex conversion.

**`cc_marketplace`** — path to the Claude Code marketplace used by marketplace reconciliation.

**`marketplace_state`** — path to repository-level marketplace state. This file is created by
`marketplace attach` and read by `marketplace sync` and `marketplace check`.

**`default_source_of_truth`** — legacy fallback for standalone converter mode.
Managed marketplace sync uses plugin-level state and does not infer direction
from staged paths.

## Example — non-standard layout

```yaml
# .plugin-cross-port.config.yaml
plugins_dir: packages
codex_marketplace: dist/codex/plugins.json
cc_marketplace: dist/claude/marketplace.json
marketplace_state: .plugin-cross-port.marketplace.json
default_source_of_truth: claude-code
```

## Precedence

Config -> marketplace state -> plugin state -> CLI flags.

Per-plugin `.plugin-cross-port.json` wins for plugin `source_of_truth`.
