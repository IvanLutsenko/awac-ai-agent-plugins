# combined-review v1.2.0 — Permissions, CodeRabbit Worktree, Agent Locale

**Date:** 2026-04-29
**Plugin:** `plugins/combined-review/`
**Version bump:** v1.1.0 → v1.2.0

## Problem

Three issues observed when running `/combined-review:review DBANK-2201 release` from a working tree on `feature/CPT-4038`:

1. **Permissions** — every `Bash(...)` call from the orchestrator command and from each of the four subagents triggered a manual approval prompt. The command's `allowed-tools` covered only a subset of what runs (`gh`, `git`, `coderabbit`, `cr`, `curl`, `which`); calls like `wc -l`, `tail -200`, `grep`, `find` fell through. Agents had no `tools:` field at all → every tool call needed approval.
2. **CodeRabbit failure** — CodeRabbit aborted with `Too many files (1025)` because the CLI reviews the working tree against `--base <target>`, but the working tree was on `feature/CPT-4038`, not on the requested source `DBANK-2201`. The CLI ended up reviewing `CPT-4038...release` (the entire long-lived diff) instead of `DBANK-2201...release`.
3. **Language inconsistency** — the language config (`system | en | ru | uk`, added in v1.1.0) translates only the final report. Agents return findings in English; orchestrator translates them in Step 6. Two-pass translation creates inconsistency and burns tokens.

## Solution overview

| Area | Change |
|------|--------|
| Permissions | Extend command `allowed-tools`; add explicit `tools:` to each agent |
| CodeRabbit | Run CodeRabbit inside a temp `git worktree` checked out to the source branch when working tree ≠ source |
| Language | Pass resolved language to each agent; agents write findings in target language; remove final-report translation pass |

## A. Permissions

### A.1 — Extend `commands/review.md` `allowed-tools`

Add the bash patterns the orchestrator actually runs:

```
Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*)
```

Final `allowed-tools` line:

```
allowed-tools: Bash(gh:*), Bash(git:*), Bash(coderabbit:*), Bash(cr:*), Bash(curl:*), Bash(which:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*), Agent, Read, Glob, Grep
```

### A.2 — Add `tools:` to each agent

Minimal whitelists per agent responsibility. Narrower than `Bash(*)` so an agent can't accidentally run destructive commands (`git push`, `rm`, etc.).

**code-reviewer:**
```yaml
tools: Read, Grep, Glob, Bash(git log:*), Bash(git blame:*), Bash(git diff:*), Bash(git show:*), Bash(grep:*), Bash(rg:*), Bash(find:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*)
```

**git-historian:**
```yaml
tools: Read, Grep, Bash(git log:*), Bash(git blame:*), Bash(git diff:*), Bash(git show:*), Bash(git rev-parse:*), Bash(git merge-base:*)
```

**silent-failure-hunter:**
```yaml
tools: Read, Grep, Glob, Bash(grep:*), Bash(rg:*), Bash(find:*), Bash(git show:*)
```

**test-analyzer:**
```yaml
tools: Read, Grep, Glob, Bash(find:*), Bash(grep:*), Bash(git show:*)
```

### Trade-off

Wider whitelists (`Bash(git:*)`, plain `Bash`) reduce future approvals if an agent grows new behaviors, but allow destructive operations. Narrow whitelists are safer at the cost of needing edits when agents legitimately need new commands. We choose narrow.

## B2. CodeRabbit via temp `git worktree`

### Detection

In Step 4, before invoking CodeRabbit, detect mismatch:

- Modes that need a worktree: `pr`, `branch-diff` (when current branch ≠ source)
- Modes that don't: `current` (uncommitted), `--base <branch>` (current branch is source by definition)

### Execution

```bash
NEED_WORKTREE=false
case "$MODE" in
  pr|branch-diff)
    [[ "$(git branch --show-current)" != "$SOURCE" ]] && NEED_WORKTREE=true
    ;;
esac

if $NEED_WORKTREE; then
  WORKTREE=$(mktemp -d -t coderabbit-XXXXXX)
  if ! git worktree add --detach "$WORKTREE" "origin/$SOURCE" 2>&1; then
    echo "CodeRabbit skipped: worktree creation failed for origin/$SOURCE"
  else
    ( cd "$WORKTREE" && coderabbit review --plain --base "origin/$TARGET" 2>&1 | tail -200 )
    git worktree remove --force "$WORKTREE" 2>/dev/null || true
  fi
else
  if [[ -n "$TARGET" ]]; then
    coderabbit review --plain --base "$TARGET" 2>&1 | tail -200
  else
    coderabbit review --plain 2>&1 | tail -200
  fi
fi
```

### Edge cases

- **`git worktree add` fails** (e.g. `origin/<source>` not fetched): print a one-line skip message; do not abort the whole review — the four agents still produce their report.
- **Cleanup fails**: not critical — temp dir is in `/tmp` and gets cleaned by the OS.
- **Source branch only exists locally** (no `origin/<source>`): `git worktree add` will fail; the skip message is acceptable. Improvement deferred.
- **Disk usage**: ~50–100 MB ephemeral for sberbankfinance0-sized repos. Acceptable.
- **Time cost**: 3–10 s for `git worktree add` on large repos.

### Why not B1 (stash + checkout)?

Originally considered. Risk: if user has uncommitted work and the command crashes mid-flight, restoring is brittle. Worktree is isolated — no chance of losing user state.

## C2. Language pass-through to agents

### Orchestrator change (`commands/review.md`)

Step 4 already builds an agent invocation. Prepend the prompt with a single line:

```
Language: <resolved>
```

Where `<resolved>` is `en`, `ru`, or `uk` (resolved in Step 0). The `system` value gets resolved to one of the three before agent launch.

Step 6 changes:
- Remove the "Write the report in the language resolved in Step 0" translation step.
- Orchestrator writes the report directly in `<resolved>`. Agent findings come in already correct.

### Agent change (all four agent files)

Add a small section to each agent's system prompt:

```markdown
## Output language

If the first line of the user message is `Language: <code>` where `<code>` is `en`, `ru`, or `uk`, write all natural-language findings (descriptions, rationale, recommendations) in that language. Keep these as-is regardless of language:
- File paths
- Code snippets
- Identifier names (class, function, variable)
- CLI commands and shell output
- Confidence/criticality numbers
```

### Trade-off

Sonnet is marginally more accurate on technical reasoning in English than Russian/Ukrainian. We accept this small quality drop in exchange for:
- Single-pass reasoning (no translate step → fewer tokens, faster, no translation drift)
- Section headers and finding bodies in same language (no English headers + Russian body mismatches)

If the quality drop becomes noticeable in practice, the per-agent prompt can be flipped back to "always reason in English; translate at the end" via a one-line edit per agent. Cheap to revert.

## File changes

```
plugins/combined-review/
  commands/review.md          # extend allowed-tools, replace Step 4 CodeRabbit block, simplify Step 6
  agents/code-reviewer.md     # add tools:, add ## Output language section
  agents/git-historian.md     # same
  agents/silent-failure-hunter.md  # same
  agents/test-analyzer.md     # same
plugin.json                    # version 1.1.0 → 1.2.0
```

No new files. No removed files.

## Test plan

Manual smoke tests after implementation:

1. **Permissions** — run `/combined-review:review` (uncommitted changes mode) on `sberbankfinance0` with a small diff. Expected: no manual approvals for routine `git`, `grep`, `find`, `wc`, `tail` calls. CodeRabbit and agents finish without prompts.
2. **CodeRabbit worktree** — repro the original case: from working tree on `feature/CPT-4038`, run `/combined-review:review DBANK-2201 release`. Expected: temp worktree created, CodeRabbit completes against `DBANK-2201...release` (~12 files, not ~1025). Worktree removed at end.
3. **Language ru** — with `.claude/combined-review.local.md` containing `language: ru`, run review on a small diff. Expected: agent findings come in Russian; final report fully in Russian; no "Critical / Findings / Tests" English headers.
4. **Language en** — same with `language: en`. Expected: report in English (existing behavior preserved).
5. **Worktree skip** — manually delete `origin/<source>` ref locally, rerun. Expected: clean skip message, agents still produce their report.

## Out of scope

- Batching for CodeRabbit — server-side limit, no client workaround
- Automatic detection of language from CLAUDE.md beyond what v1.1.0 already does
- Per-agent language overrides
- Worktree caching across runs
