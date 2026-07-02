# Decision File Format: `.plugin-cross-port.json`

Each attached plugin gets a `.plugin-cross-port.json` at its root. This file
records the plugin-level source of truth and generated files that have been
manually customized. Repository-level marketplace state lives in
`.plugin-cross-port.marketplace.json`.

## Schema

```yaml
version: 2
plugin: plugin-name
source_of_truth: claude-code
status: synced

# Files the converter must NOT overwrite (manually maintained)
manually_maintained:
  - skills/generated-from-commands/my-command/SKILL.md
  - .codex-plugin/plugin.json
```

## Fields

**`version`** — schema version. Attached plugins use `2`; legacy version `1`
files remain readable.

**`plugin`** — plugin name, matches `.claude-plugin/plugin.json`.

**`source_of_truth`** — `claude-code` or `codex`. Direction is never inferred
from changed files.

**`status`** — `synced`, `needs-review`, or `failed`.

**`manually_maintained`** — list of relative paths (from plugin root). The converter skips overwriting these. Add a path here after manually editing a generated file you want to preserve.

## Repository Marketplace State

```json
{
  "version": 1,
  "source_of_truth": "claude-code",
  "source_marketplace": ".claude-plugin/marketplace.json",
  "targets": {
    "codex": ".agents/plugins/marketplace.json"
  },
  "plugins": {
    "plugin-name": {
      "path": "plugins/plugin-name",
      "source_of_truth": "claude-code",
      "status": "synced"
    }
  }
}
```

The marketplace source owns root metadata, active plugin set, ordering, and
plugin directory removal. Plugin state owns conversion direction.

## Adaptation State

Semantic adaptation state lives at:

```text
plugins/<name>/.plugin-cross-port/adaptation-state.json
```

The file is JSON-compatible YAML:

```json
{
  "version": 1,
  "plugin": "plugin-name",
  "plan_hash": "sha256:...",
  "source_snapshot": "sha256:...",
  "status": "planned",
  "adaptations": [
    {
      "id": "hooks-sessionstart",
      "strategy": "semantic",
      "criticality": "critical",
      "rationale": "Claude Code hook SessionStart has no deterministic Codex equivalent.",
      "source_files": [".claude-plugin/plugin.json", "hooks/sessionstart.sh"],
      "target_files": ["skills/generated-from-hooks/sessionstart/SKILL.md"],
      "source_snapshot": "sha256:..."
    }
  ]
}
```

Changing a source file for a semantic adaptation makes that adaptation stale.
Stale critical adaptations set plugin status to `needs-review`; stale
non-critical adaptations remain available and emit a warning.

## Example: obsidian-tracker after conversion

```yaml
version: 2
plugin: obsidian-tracker
source_of_truth: claude-code
status: synced
manually_maintained: []
```
