# Repo-Level Config: `.plugin-cross-port.config.yaml`

Optional config file at the **repo root** (not inside a plugin directory).
If absent, all defaults apply — nothing breaks.

## Format

```yaml
plugins_dir: plugins                              # where plugins live (default: plugins)
codex_marketplace: .agents/plugins/marketplace.json  # Codex marketplace output path
default_source_of_truth: claude-code              # fallback when no decision file exists
```

## Fields

**`plugins_dir`** — directory scanned by the pre-commit hook for changed plugins.
Change this if your repo uses a non-standard layout (e.g., `packages`, `src`).

**`codex_marketplace`** — path where `convert_cc_to_codex.py` writes the Codex marketplace entry.
Change if your Codex tooling expects it elsewhere.

**`default_source_of_truth`** — used by the hook when a plugin has no `.plugin-cross-port.yaml`
and both `.claude-plugin/` and `.codex-plugin/` exist.
Values: `claude-code` (default) or `codex`.

## Example — non-standard layout

```yaml
# .plugin-cross-port.config.yaml
plugins_dir: packages
codex_marketplace: dist/codex/plugins.json
default_source_of_truth: claude-code
```

## Precedence

Config → decision file → CLI flags.

Per-plugin `.plugin-cross-port.yaml` always wins over repo config for `source_of_truth`.
CLI `--force` overrides everything.
