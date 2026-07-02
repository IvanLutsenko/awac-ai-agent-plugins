# Continuous Mode: Keeping Dual-Target in Sync

## Philosophy

- **Marketplace source of truth** is selected by `marketplace attach`. It owns
  marketplace root metadata, active plugin ordering, and removals.
- **Plugin source of truth** is stored per plugin in `.plugin-cross-port.json`.
  One plugin can be Claude Code-first while another is Codex-first.
- **Generated files are regenerated** by `marketplace sync`; manual edits on
  generated sides are rejected unless listed in `manually_maintained`.
- **Pre-commit hook enforces declared state** and stages generated output in the
  same commit.

## Pre-commit Hook

The hook lives at `.githooks/pre-commit` and runs automatically before every commit (the repo already has `core.hooksPath = .githooks`).

**Direction is determined only by plugin-level `source_of_truth`:**

- `source_of_truth: claude-code` -> CC-side files are authoritative
- `source_of_truth: codex` -> Codex-side files are authoritative
- Generated-side staged edits are rejected unless explicitly listed in
  `manually_maintained`

**What it does:**
1. Scans staged files to find changed plugins
2. Runs `cross_port.py marketplace sync --changed-only <plugins> --stage`
3. Runs full sync when the canonical marketplace file is staged
4. Stages generated output and deletions in the same commit
5. Fails the commit on generated-side edits or conversion errors

**Nothing to configure** — the hook is already wired. To verify it's active:

```bash
git config core.hooksPath   # should print: .githooks
ls .githooks/               # should list: pre-commit, pre-push
```

## Local workflow

```bash
# Attach a marketplace once
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace attach --source claude-code

# Reconcile everything
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace sync

# CI/dry-run consistency check
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace check

# Attach one plugin to an already managed repository
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin attach plugins/example --source codex

# Explicitly change a plugin's authoritative side after a clean check
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin switch-source plugins/example --to claude-code
```

## What triggers a re-sync

| Change | Re-sync needed? |
|---|---|
| Edit authoritative manifest or content | Yes — pre-commit regenerates target files |
| Edit generated manifest or content | Rejected unless manually maintained |
| Remove canonical marketplace entry | Yes — sync removes the plugin directory |
| Edit shared `skills/<name>/SKILL.md` | Depends on plugin source and target conversion |
| Edit `agents/*.md` | Yes — regenerates `skills/generated-from-agents/<name>/SKILL.md` |
| Edit hooks in `plugin.json` | Warning only — no Codex equivalent |

## Adaptation during sync

`marketplace sync` remains mechanical. It does not invent new semantic
adaptations. It only:

- replays previously approved reproducible adaptation rules;
- detects stale semantic adaptations from source snapshots;
- marks stale critical adaptations as `needs-review`;
- keeps stale non-critical adaptations available and reports a warning.

## Marking a generated file as manually maintained

After customizing a generated skill beyond what the converter produces:

```yaml
# plugins/my-plugin/.plugin-cross-port.json
manually_maintained:
  - skills/generated-from-commands/my-command/SKILL.md
```

The converter skips overwriting files listed here and emits a reminder notice instead.

## Publication asymmetry

Codex marketplace entries for failed or review-required targets use
`policy.installation: "NOT_AVAILABLE"`. Claude Code failed targets are omitted
from the Claude Code marketplace; no disabled marketplace field is assumed.
