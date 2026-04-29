---
description: "Combined code review: multi-agent analysis + CodeRabbit. Supports PR, branch diff, uncommitted changes."
argument-hint: "[PR#] | [branch1 branch2] | [--base branch] | [+comments] [+types] [+simplify] [all]"
allowed-tools: Bash(gh:*), Bash(git:*), Bash(coderabbit:*), Bash(cr:*), Bash(curl:*), Bash(which:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*), Agent, Read, Glob, Grep
---

# Combined Code Review

## Context

- Directory: !`pwd`
- Branch: !`git branch --show-current 2>/dev/null || echo "detached HEAD"`
- Has changes: !`git status --porcelain 2>/dev/null | head -1 | grep -q . && echo "yes" || echo "no"`

## Step 0 — Read config

Check if config exists at `.claude/combined-review.local.md`. If it exists, read the `language` setting from YAML frontmatter.

If config doesn't exist, use default: `language: system`.

**Language resolution:**
- `system` → detect from CLAUDE.md (look for language hints like "Отвечай", "русский", etc.) or fall back to English
- `en` / `ru` / `uk` → use directly

Apply the resolved language to the final report output (Step 6). Agents work internally in English for accuracy; only the final report is translated.

## Arguments

**$ARGUMENTS**

## Finding format

CRITICAL: every finding MUST include file path and line number: `path/to/File.kt:42`.

## Step 1 — Parse arguments

Split `$ARGUMENTS` into **mode** and **options**:

**Mode** (first argument or pair):
- Empty → current changes (uncommitted + staged)
- `--base <branch>` → current branch vs specified
- Number (`123`) → PR number
- Two branch-like arguments → diff of first relative to second (target is second)
  - `feature/X feature/Y`
  - `feature/X to feature/Y`
  - `feature/X...feature/Y`

Branch-like: contains `/`, or starts with `feature/`, `fix/`, `release/`, `hotfix/`, `master`, `main`, `develop`.

**Options** (after mode):
- `+comments` — add comment analysis
- `+types` — add type design analysis
- `+simplify` — add code simplification
- `all` — run all agents including optional

## Step 2 — Gather diff and context

Based on mode:

**PR:**
```bash
gh pr view <number>
gh pr diff <number>
```

**Branch diff:**
Try with `origin/` first, then local:
```bash
git fetch origin <branch1> <branch2> 2>/dev/null
git log origin/<target>..origin/<source> --oneline
git diff origin/<target>...origin/<source>
```
Source = first argument, target = second.

**Current changes:**
```bash
git diff HEAD
git diff --cached
```
With `--base`: `git diff <base>...HEAD`

**If diff is empty — report and stop.**

Also gather:
- List of changed files
- CLAUDE.md content (root + changed directories)

## Step 3 — CodeRabbit setup check

Before launching agents, check CodeRabbit availability:

```bash
which coderabbit 2>/dev/null
```

**If not installed:**
Ask the user: "CodeRabbit CLI not installed. Install it? (Y/n)"

If yes:
```bash
curl -fsSL https://cli.coderabbit.ai/install.sh | sh
```

If no — skip CodeRabbit, continue with 4 agents.

**If installed, check auth:**
```bash
coderabbit auth status 2>&1 | head -3
```

If not authenticated:
Tell the user: "CodeRabbit requires authentication. Run `! coderabbit auth login` in the prompt to log in via browser."
Skip CodeRabbit for this run, continue with 4 agents.

## Step 4 — Launch agents

Launch **4 default agents in parallel** + CodeRabbit (if available) + optional agents if requested.

Pass each agent: full diff, file list, CLAUDE.md content.

### Agent 1 — Code Reviewer

Launch the `code-reviewer` agent. It checks:
- CLAUDE.md compliance (with rule citations)
- Bugs: null safety, race conditions, resource leaks, logic errors
- Code quality: duplication, broken public APIs, SOLID violations

### Agent 2 — Git Historian

Launch the `git-historian` agent. It checks:
- Recent git history and blame for changed files
- Reverted fixes, hot spots, parallel work conflicts
- Lost changes (someone's code removed without justification)

### Agent 3 — Silent Failure Hunter

Launch the `silent-failure-hunter` agent. It checks:
- Empty catch blocks, broad catches
- Silent failures, swallowed errors
- Missing error context and user feedback
- Unjustified fallback behavior

### Agent 4 — Test Analyzer

Launch the `test-analyzer` agent. It checks:
- Test coverage for new/changed business logic
- Missing error path tests
- Missing boundary condition tests
- Test quality (behavior vs implementation testing)

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

### Optional agents (by request)

**+comments — Comment Analyzer (Sonnet agent):**
Check comment accuracy vs actual code. Find: comments that don't match code, stale TODOs, comment rot. Only for changed files.

**+types — Type Design Analyzer (Sonnet agent):**
For new/changed types: evaluate encapsulation, invariant expression, enforcement. Rate 1-10 per criterion.

**+simplify — Code Simplifier (Sonnet agent):**
Find areas in diff that can be simplified without losing functionality. Provide concrete before/after suggestions.

## Step 5 — Score and filter

Collect findings from all agents:

1. **Deduplicate** — if two agents found the same issue, keep one with highest confidence
2. **Filter out** confidence < 60

**False positives (skip):**
- Pre-existing issues (existed before this diff)
- Things linter/compiler/CI would catch
- Stylistic nitpicks not backed by CLAUDE.md
- Intentional functionality changes
- Generic advice without specifics ("add tests" without saying for what)
- Issues on lines not changed in this diff

## Step 6 — Final report

**Write the report in the language resolved in Step 0.** Section headers and descriptions must be in the target language. Code snippets and file paths stay as-is.

```markdown
## Code Review: [what was reviewed]

**Files:** N | **Lines:** +X / -Y | **Commits:** N

### Critical

1. `path/to/File.kt:42` — description [source: agent-name, confidence: N]
   > code or context

### Findings

1. `path/to/File.kt:100` — description [source: agent-name, confidence: N]

### Tests

1. `path/to/File.kt` — missing test for [scenario] [criticality: N/10]

### CodeRabbit

[Results deduplicated with agents. If CodeRabbit didn't run — omit this section.]

### Positive

- What's done well (2-3 points)
```

If no findings after filtering:
```markdown
## Code Review: [what was reviewed]

No issues found. Checked: CLAUDE.md, bugs, git history, error handling, tests.
```

**Do NOT post a comment to the PR automatically.** Only output to the user.
