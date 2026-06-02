# plugin-cross-port: Marketplace Reconciliation and Adaptation

**Date:** 2026-06-02
**Status:** Design approved in brainstorming, awaiting written-spec review
**Plugin:** `plugins/plugin-cross-port`

---

## 1. Goal

Extend `plugin-cross-port` from a pair of per-plugin converters into a safe
dual-target marketplace workflow.

The plugin must support:

1. one-shot conversion of a single plugin;
2. attaching an existing Claude Code or Codex marketplace and converting every
   listed plugin;
3. continuous maintenance of both ecosystems in one repository;
4. mixed repositories where one plugin is Claude Code-first and another is
   Codex-first;
5. deterministic reconciliation of both marketplace files;
6. a later, explicit planning workflow for semantic adaptations that cannot be
   derived mechanically.

Implementation is split into two releases:

- `0.6.0`: deterministic marketplace reconciliation;
- `0.7.0`: planned semantic adaptation workflow.

---

## 2. Current Gaps

The repository currently has two plugin converters:

```text
convert_cc_to_codex.py
convert_codex_to_cc.py
```

They convert one plugin directory at a time. The CC-to-Codex converter also
upserts one Codex marketplace entry. The reverse converter does not update a
marketplace.

Continuous mode is also too permissive: `.githooks/pre-commit` chooses a
direction from staged files and invokes a converter with `--force`. A manual
edit on the generated side can therefore overwrite authoritative files.

The marketplace itself is not modeled as a reconciled object:

- no attach-all operation;
- no explicit marketplace source of truth;
- no full-list reconciliation or order preservation;
- no deletion when a canonical entry disappears;
- no best-effort status report;
- no safe publication state for conversion failures;
- no dry-run consistency command suitable for CI.

---

## 3. Two Independent Sources Of Truth

### 3.1 Marketplace-level source of truth

The repository chooses one canonical marketplace when it is attached:

```yaml
# .plugin-cross-port.marketplace.yaml
version: 1
source_of_truth: claude-code
source_marketplace: .claude-plugin/marketplace.json
targets:
  codex: .agents/plugins/marketplace.json
```

or:

```yaml
source_of_truth: codex
source_marketplace: .agents/plugins/marketplace.json
targets:
  claude-code: .claude-plugin/marketplace.json
```

Marketplace-level ownership covers:

- marketplace root metadata;
- active plugin set;
- plugin ordering;
- removal of plugins from the repository.

### 3.2 Plugin-level source of truth

Every attached plugin must independently choose one authoritative ecosystem:

```yaml
# plugins/example/.plugin-cross-port.yaml
version: 2
plugin: example
source_of_truth: codex
status: synced
```

Plugin-level ownership covers:

- plugin manifest metadata: `name`, `version`, `description`, `author`;
- commands, skills, hooks, scripts and MCP configuration;
- deterministic generated output;
- adaptation state.

This permits a mixed repository:

| Plugin | Plugin source of truth | Generated direction |
|---|---|---|
| `legacy-cc-plugin` | `claude-code` | CC -> Codex |
| `new-codex-plugin` | `codex` | Codex -> CC |

The marketplace may still be CC-first. In that case a Codex-first plugin
updates its generated CC manifest and the corresponding entry in the canonical
CC marketplace. This is not a bidirectional merge: field ownership remains
explicit.

---

## 4. Marketplace Field Ownership

The useful field-level model from the earlier derivation design remains.

### 4.1 Per-plugin marketplace entries

| Field | Source | Re-sync behavior |
|---|---|---|
| `name` | authoritative plugin manifest | overwrite |
| `version` (CC only) | authoritative plugin manifest | overwrite |
| `description` (CC only) | authoritative plugin manifest | overwrite |
| `author` (CC only) | authoritative plugin manifest | overwrite |
| `source` / `source.path` | current plugin path relative to repo root | recompute |
| `category` | existing marketplace entry | preserve; default for new entry |
| Codex `policy.authentication` | existing Codex entry | preserve; default `ON_INSTALL` |
| Codex `policy.products` | existing Codex entry | preserve only when present |
| Codex `policy.installation` | reconciliation status | derive from publication state |

New Codex entries must always include:

```json
{
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Development"
}
```

Allowed Codex `policy.installation` values are:

```text
NOT_AVAILABLE
AVAILABLE
INSTALLED_BY_DEFAULT
```

### 4.2 Marketplace root fields

Ordinary plugin sync must not overwrite marketplace-level root metadata:

- catalog `name`;
- catalog `version`, `description`, `owner` when present;
- Codex `interface.displayName`;
- schema declaration.

`marketplace attach` creates missing sibling files with valid root metadata.
After creation, root fields remain marketplace-owned.

### 4.3 Current path always wins

Marketplace entry paths are recomputed from the current plugin location:

```text
./plugins/<plugin-name>
```

Copied marketplace entries and copied `.plugin-cross-port.yaml` files are not
trusted as path sources.

---

## 5. Release 0.6.0: Deterministic Marketplace Reconciliation

### 5.1 CLI contract

Introduce a single deterministic entry point:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py <command>
```

Commands:

```bash
# Attach an existing marketplace and convert all listed plugins.
cross-port marketplace attach --source claude-code
cross-port marketplace attach --source codex

# Reconcile generated files, statuses and target marketplace.
cross-port marketplace sync

# Dry-run reconcile. Exit non-zero when repository output is stale or invalid.
cross-port marketplace check

# Convert one plugin without opting into continuous marketplace management.
cross-port plugin convert plugins/example --from claude-code --to codex

# Attach one plugin to an already managed repository.
cross-port plugin attach plugins/example --source codex

# Explicitly change the authoritative side.
cross-port plugin switch-source plugins/example --to claude-code
```

`plugin convert` remains suitable for standalone or throwaway directories.
If no repository marketplace state exists, it converts plugin files but does
not create marketplace files.

### 5.2 Marketplace attach

`marketplace attach`:

1. validates the selected canonical marketplace;
2. creates `.plugin-cross-port.marketplace.yaml`;
3. enumerates every canonical marketplace entry in order;
4. resolves each local plugin directory from the entry;
5. writes plugin-level state, defaulting each plugin source to the selected
   marketplace source;
6. performs deterministic conversion for every plugin;
7. creates or updates the sibling marketplace;
8. reports all successes, review requirements and failures.

The default is all plugins. Optional narrowing remains available:

```bash
cross-port marketplace attach --source claude-code --exclude crashlytics,drawbridge
cross-port marketplace attach --source claude-code --only obsidian-tracker
```

Attach is best effort. A failed plugin is rolled back to its pre-attempt
target state while successful plugins remain synchronized.

### 5.3 Marketplace sync

`marketplace sync` is a full reconcile:

```text
canonical marketplace
  -> active plugin set and order
  -> plugin-level source_of_truth
  -> deterministic conversion
  -> publication status
  -> generated sibling marketplace
```

For each active plugin:

1. read plugin state;
2. convert only from the declared authoritative side;
3. regenerate converter-owned files;
4. preserve explicitly manually maintained files;
5. update manifest-owned metadata in both marketplace entries;
6. recompute source paths;
7. preserve non-derived fields;
8. update plugin status.

If an entry disappears from the canonical marketplace, sync removes:

```text
plugins/<name>/
```

and removes the sibling marketplace entry. Git is the recovery mechanism for
mistaken deletions. No detached state is retained.

Deletion is allowed only after resolving a local path under the configured
`plugins_dir` and confirming that the resolved directory name matches the
plugin name. A malformed, external or escaping path is a hard error and is
never deleted.

### 5.4 Marketplace check

`marketplace check` executes the same reconcile logic without writes. It exits
non-zero when:

- generated files are stale;
- either marketplace differs from expected output;
- an active plugin is `needs-review` or `failed`;
- a manifest is invalid;
- a plugin path cannot be resolved;
- a generated-side manual edit violates ownership.

This command is the CI entry point.

### 5.5 Best-effort statuses and publication

Plugin state:

```yaml
status: synced
status: needs-review
status: failed
```

Rules:

| Status | Codex target entry | CC target entry |
|---|---|---|
| `synced` | publish with `AVAILABLE` | publish |
| `needs-review` | publish with `NOT_AVAILABLE` | omit |
| `failed` | publish with `NOT_AVAILABLE` | omit |

Codex has a validated availability field. The current CC marketplace schema
has no confirmed equivalent, so broken generated CC plugins must not be
published. Their errors remain visible in state and command output.

Example failure state:

```yaml
plugins:
  crashlytics:
    status: failed
    target: codex
    last_error: "manifest validation failed"
```

### 5.6 Pre-commit integration

Replace direction guessing with a thin reconcile call:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace sync \
  --repo-root "$REPO_ROOT" \
  --changed-only \
  --stage
```

The hook:

1. reads staged files;
2. resolves affected attached plugins;
3. reads plugin-level `source_of_truth`;
4. rejects edits on generated files unless explicitly marked
   `manually_maintained`;
5. converts only from the authoritative side;
6. updates both marketplace files;
7. stages additions, updates and removals.

It must not use `--force` to flip direction implicitly.

Example rejection:

```text
ERROR: plugins/example/.codex-plugin/plugin.json is generated.
Source of truth: claude-code.
Edit .claude-plugin/plugin.json or run:
cross-port plugin switch-source plugins/example --to codex
```

---

## 6. One-shot Vendor Workflow

Cross-repository copying is not part of the deterministic converter because it
requires judgment:

- preserve license and attribution;
- resolve name collisions;
- decide whether to retain upstream history;
- discard stale foreign generated output;
- explicitly choose plugin source of truth when attaching.

The interactive skill handles the vendor phase:

```text
1. Copy external plugin into plugins/<name>.
2. Review license, attribution and collisions.
3. Remove stale foreign generated artifacts after review.
4. Run plugin convert for a one-shot port, or plugin attach for continuous mode.
```

---

## 7. Release 0.7.0: Planned Semantic Adaptation

Mechanical conversion cannot fully preserve behavior when ecosystems have no
direct equivalent. Examples include runtime hooks, tool identifiers,
permission behavior and ecosystem-specific paths.

Adaptation is intentionally separate from bulk attach:

```bash
# Analyze only. Writes a plan and source snapshot.
cross-port plugin adapt plugins/example

# Apply the previously reviewed plan atomically.
cross-port plugin adapt plugins/example --apply
```

Generated files:

```text
plugins/example/.plugin-cross-port/
  adaptation-plan.md
  adaptation-state.yaml
```

State records:

```yaml
plan_hash: sha256:...
source_snapshot: sha256:...
status: planned
adaptations:
  - id: session-start-fallback
    strategy: semantic
    criticality: critical
    rationale: "Without initialization, MCP tools cannot resolve configuration"
    source_files:
      - hooks/session-start.sh
      - .claude-plugin/plugin.json
    target_files:
      - skills/setup/SKILL.md
```

Rules:

1. `adapt` analyzes and writes a plan but does not modify target files.
2. `adapt --apply` applies the whole approved plan, not one decision at a time.
3. `--apply` rejects a stale source snapshot.
4. Reproducible adaptation rules are replayed automatically by sync.
5. If a source file for a semantic adaptation changes, that adaptation becomes
   stale.
6. A stale critical semantic adaptation sets `needs-review` and makes the
   generated target unavailable.
7. A stale non-critical semantic adaptation leaves the target available and
   emits a warning.

Bulk marketplace attach in `0.6.0` does not invoke LLM adaptation.

---

## 8. Internal Architecture

### 8.1 Shared deterministic modules

Extract focused modules:

```text
scripts/cross_port.py             # CLI routing
scripts/marketplace_sync.py       # marketplace root and entry reconciliation
scripts/plugin_state.py           # marketplace and per-plugin state I/O
scripts/reconcile.py              # attach/sync/check orchestration
scripts/convert_cc_to_codex.py    # per-plugin CC -> Codex transformation
scripts/convert_codex_to_cc.py    # per-plugin Codex -> CC transformation
```

`marketplace_sync.py` should expose pure functions where possible:

- compute marketplace paths;
- seed valid sibling marketplace root metadata;
- recompute plugin source path;
- preserve ordered entries;
- upsert CC entry;
- upsert Codex entry;
- mark Codex entry `NOT_AVAILABLE`;
- remove entries absent from canonical marketplace.

### 8.2 Root metadata seeding

A newly generated Codex marketplace must include:

```json
{
  "name": "catalog-name",
  "interface": {
    "displayName": "Catalog Name"
  },
  "plugins": []
}
```

A newly generated CC marketplace must include valid CC root metadata copied or
derived from the canonical catalog where possible. Unknown optional fields are
omitted rather than invented.

### 8.3 State files

Root state owns repository orchestration:

```text
.plugin-cross-port.marketplace.yaml
```

Plugin state owns conversion direction and plugin-local status:

```text
plugins/<name>/.plugin-cross-port.yaml
```

The existing minimal YAML implementation may be extended only for the schema
actually written by these files. Do not add a runtime PyYAML dependency.

---

## 9. Required Tests

### 9.1 Shared marketplace sync

- seed valid Codex root metadata;
- preserve marketplace root metadata;
- recompute paths from current plugin location;
- preserve `category`, authentication policy and optional products;
- derive installation availability from status;
- preserve canonical plugin order;
- remove stale sibling entries;
- reject plugin paths outside repo root.

### 9.2 Attach and reconcile

- attach CC-first marketplace and convert all plugins;
- attach Codex-first marketplace and generate CC sibling;
- mixed CC-first and Codex-first plugins;
- metadata from Codex-first plugin updates canonical CC entry;
- best-effort sync preserves successful plugins when one fails;
- failed Codex target is `NOT_AVAILABLE`;
- failed CC target is omitted;
- deleted canonical entry removes the entire plugin directory;
- malformed or escaping deletion path is rejected without filesystem changes;
- `check` detects stale output without writes.

### 9.3 Hook safety

- authoritative-side edit regenerates target;
- generated-side edit is rejected;
- explicit `switch-source` permits a direction change;
- staged deletions are included;
- changed-only sync touches only affected plugins plus marketplaces.

### 9.4 Existing regressions

Retain coverage for:

- stale generated skill cleanup;
- stale generated CC command cleanup;
- plugin-root-relative `manually_maintained`;
- one-shot converter idempotency;
- standalone plugin conversion without marketplace creation.

---

## 10. Documentation Changes

Update:

- `plugins/plugin-cross-port/README.md`;
- `references/mapping.md`;
- `references/continuous-mode.md`;
- `references/decision-file.md`;
- `references/config.md`;
- `skills/cc-to-codex/SKILL.md`;
- `skills/codex-to-cc/SKILL.md`;
- `skills/maintain-dual-target/SKILL.md`;
- root `CLAUDE.md` release checklist.

For attached dual-target plugins, manual marketplace version updates disappear:
reconciliation derives per-plugin metadata from the authoritative manifest.

---

## 11. Non-Goals

### 0.6.0

- automatic LLM adaptation during bulk attach;
- cross-repository copying inside deterministic scripts;
- implicit source-of-truth switching;
- manual mode where the hook validates but never synchronizes;
- preserving removed plugin directories after canonical removal.

### 0.7.0

- applying an adaptation plan without explicit `--apply`;
- per-decision interactive approval after the whole plan was reviewed;
- pretending that every runtime hook has an equivalent.

---

## 12. Verified Schema Notes

The Codex marketplace contract was checked against the local `plugin-creator`
reference before writing this design:

- root `name` is required;
- `interface.displayName` is seeded for new marketplace files;
- plugin order in `plugins[]` is render order;
- each entry includes `policy.installation`, `policy.authentication` and
  `category`;
- allowed installation values are `NOT_AVAILABLE`, `AVAILABLE` and
  `INSTALLED_BY_DEFAULT`;
- allowed authentication values are `ON_INSTALL` and `ON_USE`.

The CC marketplace examples were checked against the current Anthropic
`anthropics/claude-code` repository. No publication-policy field equivalent to
Codex `NOT_AVAILABLE` was confirmed.
