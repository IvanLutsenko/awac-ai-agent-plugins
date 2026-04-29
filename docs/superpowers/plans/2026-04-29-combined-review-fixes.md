# combined-review v1.2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three issues in `plugins/combined-review/`: (1) excessive manual permission prompts during command + subagent runs, (2) CodeRabbit aborts when working tree branch ≠ reviewed source branch, (3) language config translates only the final report instead of being applied to agent output.

**Architecture:** Edit-only changes inside `plugins/combined-review/`. No new files. Permissions handled via `allowed-tools` (command) and `tools:` frontmatter (4 agents). CodeRabbit fix uses a temp `git worktree` checked out to the source branch so the CLI sees the correct diff. Language passed as `Language: <code>` first line of each agent's prompt; agents emit findings in that language; orchestrator skips final translation pass.

**Tech Stack:** Claude Code plugin (markdown commands + agents), bash for worktree procedure, JSON for plugin manifest.

**Spec:** [`docs/superpowers/specs/2026-04-29-combined-review-fixes-design.md`](../specs/2026-04-29-combined-review-fixes-design.md)

---

## File Structure

All paths relative to `~/projects/awac-claude-code-plugins/`.

| File | Change |
|------|--------|
| `plugins/combined-review/commands/review.md` | Extend `allowed-tools`; replace Step 4 CodeRabbit block; inject `Language:` line into agent prompts; simplify Step 6 |
| `plugins/combined-review/agents/code-reviewer.md` | Add `tools:` frontmatter; append `## Output language` section |
| `plugins/combined-review/agents/git-historian.md` | Same as above |
| `plugins/combined-review/agents/silent-failure-hunter.md` | Same as above |
| `plugins/combined-review/agents/test-analyzer.md` | Same as above |
| `plugins/combined-review/.claude-plugin/plugin.json` | Bump `version` 1.0.0 → 1.2.0 |

This plugin has no automated test suite. Verification is manual smoke testing per the spec test plan, performed at the end (Task 8).

---

## Task 1: Extend `allowed-tools` in review command

**Files:**
- Modify: `plugins/combined-review/commands/review.md:1-5`

- [ ] **Step 1: Read the current frontmatter**

```bash
sed -n '1,5p' ~/projects/awac-claude-code-plugins/plugins/combined-review/commands/review.md
```

Expected output:
```
---
description: "Combined code review: multi-agent analysis + CodeRabbit. Supports PR, branch diff, uncommitted changes."
argument-hint: "[PR#] | [branch1 branch2] | [--base branch] | [+comments] [+types] [+simplify] [all]"
allowed-tools: Bash(gh:*), Bash(git:*), Bash(coderabbit:*), Bash(cr:*), Bash(curl:*), Bash(which:*), Agent, Read, Glob, Grep
---
```

- [ ] **Step 2: Replace `allowed-tools` line**

In `plugins/combined-review/commands/review.md`, replace:
```
allowed-tools: Bash(gh:*), Bash(git:*), Bash(coderabbit:*), Bash(cr:*), Bash(curl:*), Bash(which:*), Agent, Read, Glob, Grep
```

with:
```
allowed-tools: Bash(gh:*), Bash(git:*), Bash(coderabbit:*), Bash(cr:*), Bash(curl:*), Bash(which:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*), Agent, Read, Glob, Grep
```

- [ ] **Step 3: Verify**

```bash
grep '^allowed-tools:' ~/projects/awac-claude-code-plugins/plugins/combined-review/commands/review.md
```

Expected: line contains `Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*)`.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/awac-claude-code-plugins
git add plugins/combined-review/commands/review.md
git commit -m "fix(combined-review): расширил allowed-tools — wc/head/tail/cat/find/grep/rg/mktemp"
```

---

## Task 2: Add `tools:` to code-reviewer agent

**Files:**
- Modify: `plugins/combined-review/agents/code-reviewer.md:1-5`

- [ ] **Step 1: Read current frontmatter**

```bash
sed -n '1,5p' ~/projects/awac-claude-code-plugins/plugins/combined-review/agents/code-reviewer.md
```

Expected: 5-line frontmatter with `name`, `description`, `model: sonnet`, `color: green`, no `tools:`.

- [ ] **Step 2: Insert `tools:` line before `model:`**

In `plugins/combined-review/agents/code-reviewer.md`, find `model: sonnet` and insert above it:
```
tools: Read, Grep, Glob, Bash(git log:*), Bash(git blame:*), Bash(git diff:*), Bash(git show:*), Bash(grep:*), Bash(rg:*), Bash(find:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*)
```

Resulting frontmatter (first 6 lines):
```
---
name: code-reviewer
description: "..."
tools: Read, Grep, Glob, Bash(git log:*), Bash(git blame:*), Bash(git diff:*), Bash(git show:*), Bash(grep:*), Bash(rg:*), Bash(find:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*)
model: sonnet
color: green
---
```

- [ ] **Step 3: Verify**

```bash
grep '^tools:' ~/projects/awac-claude-code-plugins/plugins/combined-review/agents/code-reviewer.md
```

Expected: one line starting with `tools: Read, Grep, Glob, Bash(git log:*)`.

- [ ] **Step 4: Commit (deferred)** — combine with Tasks 3, 4, 5 in single commit at end of Task 5.

---

## Task 3: Add `tools:` to git-historian agent

**Files:**
- Modify: `plugins/combined-review/agents/git-historian.md:1-5`

- [ ] **Step 1: Insert `tools:` line before `model:`**

In `plugins/combined-review/agents/git-historian.md`, find `model: sonnet` and insert above it:
```
tools: Read, Grep, Bash(git log:*), Bash(git blame:*), Bash(git diff:*), Bash(git show:*), Bash(git rev-parse:*), Bash(git merge-base:*)
```

- [ ] **Step 2: Verify**

```bash
grep '^tools:' ~/projects/awac-claude-code-plugins/plugins/combined-review/agents/git-historian.md
```

Expected: line starting with `tools: Read, Grep, Bash(git log:*)`.

---

## Task 4: Add `tools:` to silent-failure-hunter agent

**Files:**
- Modify: `plugins/combined-review/agents/silent-failure-hunter.md:1-5`

- [ ] **Step 1: Insert `tools:` line before `model:`**

In `plugins/combined-review/agents/silent-failure-hunter.md`, find `model: sonnet` and insert above it:
```
tools: Read, Grep, Glob, Bash(grep:*), Bash(rg:*), Bash(find:*), Bash(git show:*)
```

- [ ] **Step 2: Verify**

```bash
grep '^tools:' ~/projects/awac-claude-code-plugins/plugins/combined-review/agents/silent-failure-hunter.md
```

Expected: line starting with `tools: Read, Grep, Glob, Bash(grep:*)`.

---

## Task 5: Add `tools:` to test-analyzer agent + commit

**Files:**
- Modify: `plugins/combined-review/agents/test-analyzer.md:1-5`

- [ ] **Step 1: Insert `tools:` line before `model:`**

In `plugins/combined-review/agents/test-analyzer.md`, find `model: sonnet` and insert above it:
```
tools: Read, Grep, Glob, Bash(find:*), Bash(grep:*), Bash(git show:*)
```

- [ ] **Step 2: Verify all 4 agents have `tools:`**

```bash
grep -l '^tools:' ~/projects/awac-claude-code-plugins/plugins/combined-review/agents/*.md | wc -l
```

Expected: `4`.

- [ ] **Step 3: Commit Tasks 2-5 together**

```bash
cd ~/projects/awac-claude-code-plugins
git add plugins/combined-review/agents/code-reviewer.md \
        plugins/combined-review/agents/git-historian.md \
        plugins/combined-review/agents/silent-failure-hunter.md \
        plugins/combined-review/agents/test-analyzer.md
git commit -m "fix(combined-review): добавил tools: в frontmatter всех 4 агентов"
```

---

## Task 6: Add `## Output language` section to all 4 agents

**Files:**
- Modify: `plugins/combined-review/agents/code-reviewer.md` (append at end)
- Modify: `plugins/combined-review/agents/git-historian.md` (append at end)
- Modify: `plugins/combined-review/agents/silent-failure-hunter.md` (append at end)
- Modify: `plugins/combined-review/agents/test-analyzer.md` (append at end)

- [ ] **Step 1: Define the section content**

This identical block goes at the end of each of the 4 agent files (after a blank line):

```markdown

## Output language

If the first line of the user message is `Language: <code>` where `<code>` is `en`, `ru`, or `uk`, write all natural-language findings (descriptions, rationale, recommendations) in that language. Keep these as-is regardless of language:
- File paths
- Code snippets
- Identifier names (class, function, variable)
- CLI commands and shell output
- Confidence/criticality numbers

If no `Language:` line is present, default to English.
```

- [ ] **Step 2: Append to each of the 4 agents**

For each of `code-reviewer.md`, `git-historian.md`, `silent-failure-hunter.md`, `test-analyzer.md`, append the block above.

- [ ] **Step 3: Verify**

```bash
grep -c '^## Output language' ~/projects/awac-claude-code-plugins/plugins/combined-review/agents/*.md
```

Expected: each of the 4 files reports `1`.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/awac-claude-code-plugins
git add plugins/combined-review/agents/*.md
git commit -m "feat(combined-review): агенты пишут findings в языке из Language: префикса"
```

---

## Task 7: CodeRabbit via temp git worktree (Step 4 in review.md)

**Files:**
- Modify: `plugins/combined-review/commands/review.md` (Step 4, "Agent 5 — CodeRabbit (if available)" subsection, currently around lines 151-156)

- [ ] **Step 1: Locate the existing CodeRabbit subsection**

Read `plugins/combined-review/commands/review.md` lines 150-160. The current subsection is:
````markdown
### Agent 5 — CodeRabbit (if available)

```bash
coderabbit review --plain
```
Or with base branch: `coderabbit review --plain --base <branch>`
````

- [ ] **Step 2: Replace with worktree-aware version**

Replace the entire `### Agent 5 — CodeRabbit (if available)` subsection (header + the bash block + the "Or with base branch" line) with:

````markdown
### Agent 5 — CodeRabbit (if available)

CodeRabbit reviews the working tree against `--base <target>`. If the working tree is on a branch other than the source we're reviewing (PR mode or branch-diff mode where current branch ≠ source), run CodeRabbit inside a temp git worktree checked out to the source branch.

**Determine which path to take:**
- `current` mode (uncommitted changes) → run in cwd, no worktree, no `--base`.
- `--base <X>` mode → run in cwd with `--base <X>`. Current branch IS source.
- `pr` mode and `branch-diff` mode → if `git branch --show-current` differs from the source branch, use the worktree path. Otherwise run in cwd with `--base <target>`.

**Worktree path (when needed):**

Substitute `<source>` and `<target>` with the resolved branch names from Step 1.

```bash
WORKTREE=$(mktemp -d -t coderabbit-XXXXXX)
if git worktree add --detach "$WORKTREE" "origin/<source>" 2>&1; then
  ( cd "$WORKTREE" && coderabbit review --plain --base "origin/<target>" 2>&1 | tail -200 )
  git worktree remove --force "$WORKTREE" 2>/dev/null || true
else
  echo "CodeRabbit skipped: worktree creation failed for origin/<source>"
fi
```

**In-cwd path (when current branch is the source):**

```bash
coderabbit review --plain --base <target> 2>&1 | tail -200
```

Or, in `current` mode:
```bash
coderabbit review --plain 2>&1 | tail -200
```

**If `git worktree add` fails or CodeRabbit aborts**, do not fail the review — log the skip reason and continue with the 4 agents' output.
````

- [ ] **Step 3: Verify**

```bash
grep -A 2 '^### Agent 5' ~/projects/awac-claude-code-plugins/plugins/combined-review/commands/review.md | head -5
```

Expected: header followed by the new descriptive paragraph (not the old `coderabbit review --plain` one-liner).

- [ ] **Step 4: Commit**

```bash
cd ~/projects/awac-claude-code-plugins
git add plugins/combined-review/commands/review.md
git commit -m "fix(combined-review): CodeRabbit запускается в temp git worktree если working tree ≠ source"
```

---

## Task 8: Language pass-through in orchestrator (Step 4 + Step 6 of review.md)

**Files:**
- Modify: `plugins/combined-review/commands/review.md` (Step 4 intro, around lines 115-120; Step 6, around lines 184-186)

- [ ] **Step 1: Update Step 4 intro to inject Language: prefix**

Locate this block (around line 115-119):
````markdown
## Step 4 — Launch agents

Launch **4 default agents in parallel** + CodeRabbit (if available) + optional agents if requested.

Pass each agent: full diff, file list, CLAUDE.md content.
````

Replace with:
````markdown
## Step 4 — Launch agents

Launch **4 default agents in parallel** + CodeRabbit (if available) + optional agents if requested.

Pass each agent a prompt whose **first line** is `Language: <resolved>` where `<resolved>` is the language from Step 0 (`en`, `ru`, or `uk` — never literal `system`; resolve `system` to one of the three before launching). After that line, pass: full diff, file list, CLAUDE.md content.

Example agent prompt skeleton:
```
Language: ru

<diff>
...
</diff>

Changed files:
...

CLAUDE.md:
...
```
````

- [ ] **Step 2: Simplify Step 6 — remove translation pass**

Locate this block (around line 184-186):
```markdown
## Step 6 — Final report

**Write the report in the language resolved in Step 0.** Section headers and descriptions must be in the target language. Code snippets and file paths stay as-is.
```

Replace with:
```markdown
## Step 6 — Final report

Agent findings already arrive in the resolved language (via the `Language:` prefix from Step 4). Write the report shell — section headers, summary line, recommendation order — in the same resolved language. Code snippets, file paths, identifier names, and CLI commands stay as-is.
```

- [ ] **Step 3: Verify**

```bash
grep -n 'Language:' ~/projects/awac-claude-code-plugins/plugins/combined-review/commands/review.md
```

Expected: at least 2 hits — one in Step 4 intro, one in the example skeleton, optionally Step 6.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/awac-claude-code-plugins
git add plugins/combined-review/commands/review.md
git commit -m "feat(combined-review): язык пробрасывается агентам через Language: префикс, отчёт без перевода-постфакта"
```

---

## Task 9: Bump plugin version to 1.2.0

**Files:**
- Modify: `plugins/combined-review/.claude-plugin/plugin.json:4`

- [ ] **Step 1: Read current version**

```bash
grep '"version":' ~/projects/awac-claude-code-plugins/plugins/combined-review/.claude-plugin/plugin.json
```

Expected: `  "version": "1.0.0",`

- [ ] **Step 2: Replace version**

Change `"version": "1.0.0"` to `"version": "1.2.0"`.

- [ ] **Step 3: Verify**

```bash
grep '"version":' ~/projects/awac-claude-code-plugins/plugins/combined-review/.claude-plugin/plugin.json
```

Expected: `  "version": "1.2.0",`

- [ ] **Step 4: Commit**

```bash
cd ~/projects/awac-claude-code-plugins
git add plugins/combined-review/.claude-plugin/plugin.json
git commit -m "chore(combined-review): bump version to 1.2.0"
```

---

## Task 10: Manual smoke test

This task has no commits — it's verification. If any step fails, stop and report; don't ship.

- [ ] **Step 1: Permissions check (uncommitted mode)**

In a Claude Code session opened on `sberbankfinance0` (or any active branch with a small uncommitted diff), run:
```
/combined-review:review
```

Expected:
- No manual approval prompts for routine `git`, `grep`, `find`, `wc`, `tail`, `cat` calls during diff gathering.
- The 4 agents launch without per-Bash approval prompts.
- CodeRabbit either runs cleanly or reports an authentication/installation issue (acceptable).

If multiple permission prompts still appear, note which patterns are missing from `allowed-tools` / agent `tools:` and add them in a follow-up commit before proceeding.

- [ ] **Step 2: CodeRabbit worktree check**

In a Claude Code session on `sberbankfinance0` (working tree on any branch other than `DBANK-2201`), run:
```
/combined-review:review DBANK-2201 release
```

Expected:
- A temp directory under `/tmp/coderabbit-*` is created.
- CodeRabbit runs against `DBANK-2201...release` (~12 files), not `<current-branch>...release` (~1000+ files).
- After CodeRabbit finishes, the temp worktree is removed (`git worktree list` shows none lingering).

If CodeRabbit still fails with "Too many files" or the worktree is left behind, debug:
```bash
git worktree list
ls /tmp/coderabbit-*
```

- [ ] **Step 3: Language=ru check**

Create a temp config in `sberbankfinance0`:
```bash
mkdir -p ~/StudioProjects/sberbankfinance0/.claude
cat > ~/StudioProjects/sberbankfinance0/.claude/combined-review.local.md <<'EOF'
---
language: ru
---
EOF
```

Run `/combined-review:review` on a small diff.

Expected:
- Agent findings come back in Russian (descriptions, rationale).
- File paths and code snippets are unchanged.
- Section headers in the final report (e.g., "Critical / Findings / Tests") are in Russian.

Cleanup:
```bash
rm ~/StudioProjects/sberbankfinance0/.claude/combined-review.local.md
```

- [ ] **Step 4: Worktree skip check (negative path)**

Simulate the failure mode by running with a source branch that has no `origin/` ref:
```
/combined-review:review feature/nonexistent-branch release
```

Expected:
- Step 4 does not crash.
- A line like `CodeRabbit skipped: worktree creation failed for origin/feature/nonexistent-branch` appears in output.
- The 4 agents still produce their findings.

- [ ] **Step 5: Final report**

Once Steps 1–4 all behave as expected, the implementation is complete.

If anything diverged, file follow-up commits before declaring done.
