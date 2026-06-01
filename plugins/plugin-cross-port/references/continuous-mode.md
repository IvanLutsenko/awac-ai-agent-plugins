# Continuous Mode: Keeping Dual-Target in Sync

## Philosophy

- **Claude Code is source of truth** — never edit Codex-generated files directly unless you mark them `manually_maintained`.
- **Generated files are regenerated** on each converter run; manual edits are overwritten.
- **Pre-commit hook enforces sync** — Codex files are always up-to-date in the same commit as the CC changes.

## Pre-commit Hook

The hook lives at `.githooks/pre-commit` and runs automatically before every commit (the repo already has `core.hooksPath = .githooks`).

**Direction is determined by `source_of_truth` in `.plugin-cross-port.yaml`:**

- `source_of_truth: claude-code` → CC-side changes trigger `convert_cc_to_codex.py`
- `source_of_truth: codex` → Codex-side changes trigger `convert_codex_to_cc.py`
- No `.plugin-cross-port.yaml` → inferred from which manifest exists (CC manifest → `claude-code`, Codex-only → `codex`)

**What it does:**
1. Scans staged files to find changed plugins
2. Reads `source_of_truth` for each plugin
3. Detects changes on the authoritative side (ignores generated files)
4. Runs the appropriate converter with `--force`
5. Stages all generated output in the same commit
6. Fails the commit if conversion errors out

**Nothing to configure** — the hook is already wired. To verify it's active:

```bash
git config core.hooksPath   # should print: .githooks
ls .githooks/               # should list: pre-commit, pre-push
```

## Local workflow

```bash
# Run conversion manually (preview)
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --dry-run

# Run conversion manually (apply)
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root .

# Force overwrite including manually_maintained files
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --force

# Strict: fail if agents/hooks are unresolved in .plugin-cross-port.yaml
python3 plugins/plugin-cross-port/scripts/convert_cc_to_codex.py plugins/obsidian-tracker --repo-root . --strict
```

## What triggers a re-sync

| Change | Re-sync needed? |
|---|---|
| Edit `commands/*.md` | Yes — pre-commit regenerates corresponding skill |
| Add new command | Yes — pre-commit creates new generated skill |
| Delete command | Yes — pre-commit removes generated skill |
| Edit `skills/<name>/SKILL.md` | No — shared file, no generation |
| Edit `.claude-plugin/plugin.json` | Yes — version synced to Codex manifest |
| Edit `agents/*.md` | Warning only — manual action required |
| Edit hooks in `plugin.json` | Warning only — no Codex equivalent |

## Marking a generated file as manually maintained

After customizing a generated skill beyond what the converter produces:

```yaml
# plugins/my-plugin/.plugin-cross-port.yaml
manually_maintained:
  - skills/generated-from-commands/my-command/SKILL.md
```

The converter skips overwriting files listed here and emits a reminder notice instead.
