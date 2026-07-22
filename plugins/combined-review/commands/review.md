---
description: "Combined code review: multi-agent analysis + CodeRabbit. Supports GitHub PR, GitLab MR, branch diff, uncommitted changes."
argument-hint: "[PR#|!MR#] | [branch1 branch2] | [--base branch] | [+comments] [+types] [+simplify] [+threads] [all]"
allowed-tools: Bash(gh:*), Bash(glab:*), Bash(git:*), Bash(coderabbit:*), Bash(cr:*), Bash(curl:*), Bash(python3:*), Bash(which:*), Bash(wc:*), Bash(head:*), Bash(tail:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*), Agent, Read, Glob, Grep
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
- Number (`123`) → **PR/MR number**. Detect the forge from `git remote get-url origin`:
  - host contains `github` → GitHub PR (use `gh`)
  - host contains `gitlab` → GitLab MR (use `glab`)
- `!123` or a `.../-/merge_requests/123` URL → **GitLab MR** explicitly (use `glab`, repo = the MR's project)
- Two branch-like arguments → diff of first relative to second (target is second)
  - `feature/X feature/Y`
  - `feature/X to feature/Y`
  - `feature/X...feature/Y`

Branch-like: contains `/`, or starts with `feature/`, `fix/`, `release/`, `hotfix/`, `master`, `main`, `develop`.

> `!N` is zsh-escaped as `\!N` when typed — the literal mode value is `!N`. If `gh`/`glab` returns 404 for a bare number, you likely picked the wrong forge — re-check the origin host.

**Options** (after mode):
- `+comments` — add comment analysis
- `+types` — add type design analysis
- `+simplify` — add code simplification
- `+threads` — after the report, post findings as inline resolvable threads on the MR/PR (GitLab MR only; see Step 7). Opt-in — never post without this flag or an explicit request.
- `all` — run all agents including optional

## Step 2 — Gather diff and context

Based on mode:

**GitHub PR:**
```bash
gh pr view <number>
gh pr diff <number>
```

**GitLab MR** (repo path from origin, e.g. `group/project`; the MR may live on a different project — pass `-R <group/project>`):
```bash
glab mr view <iid> -R <group/project>                 # title, source→target, pipeline
git fetch origin <source> <target> 2>/dev/null
git diff origin/<target>...origin/<source> > /tmp/mr<iid>.diff   # save the diff
git log origin/<target>..origin/<source> --oneline
```
Read `source`/`target` from the `glab mr view` output (`<source> -> <target>`). The working tree is usually on a *different* branch than the MR — do not read file context from cwd; create a detached worktree at the MR source (see Step 5) and read context from there.

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

> **CLI ≥ 0.7:** `--plain` was removed (plain text is the default) — passing it errors out. Do **not** use `--plain`. Free plan caps a review at **150 changed files**; for larger diffs split by directory (see Agent 5).

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
  ( cd "$WORKTREE" && coderabbit review --base "origin/<target>" 2>&1 | tail -200 )
  git worktree remove --force "$WORKTREE" 2>/dev/null || true
else
  echo "CodeRabbit skipped: worktree creation failed for origin/<source>"
fi
```

**In-cwd path (when current branch is the source):**

```bash
coderabbit review --base <target> 2>&1 | tail -200
```

Or, in `current` mode:
```bash
coderabbit review 2>&1 | tail -200
```

**Large diffs (> 150 changed files, free-plan limit).** A single `coderabbit review` aborts with `Too many files!`. Split by directory so each bucket is < 150 files and run once per bucket (in the same worktree/cwd), then merge findings:
```bash
# bucket the changed paths, e.g. by top-level dir:
git diff origin/<target>...origin/<source> --name-only | awk -F/ '{print $1}' | sort | uniq -c
# then, per bucket that keeps each run under 150 files:
coderabbit review --base origin/<target> --dir core    2>&1 | tail -200
coderabbit review --base origin/<target> --dir feature 2>&1 | tail -200
```
Pick bucket boundaries (a top-level dir, or a couple grouped together) so every run stays < 150. Note in the report which paths, if any, fell outside the buckets and were not CodeRabbit-reviewed.

**If `git worktree add` fails or CodeRabbit aborts** (including a too-many-files error you chose not to split), do not fail the review — log the skip reason and continue with the 4 agents' output.

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
3. **Scope check** — for every finding, verify the cited `file:line` is in the diff (added or modified). Run `grep` on the saved diff file if unsure. If the line is not in the diff, drop the finding even if multiple agents reported it. Reading-for-context is fine; reporting-on-unchanged-code is not.
4. **Race-condition sanity check** — if any finding flags an `init { launch { x = suspendRead() } }` + later sync read pattern as Critical or Warning, demand the time-window estimate. If the finding doesn't quantify producer-time (typically ms for DataStore/prefs) vs consumer-time (the realistic user steps before x is read), downgrade severity or drop. Pattern-based race claims without timing are false positives.
5. **Parallel-conflict sanity check** — if a finding cites a parallel branch/commit as a conflict source, verify with `git merge-base --is-ancestor <commit> origin/<target>`. If the commit is already in target, drop the finding.

**False positives (skip):**
- Pre-existing issues (existed before this diff)
- Things linter/compiler/CI would catch
- Stylistic nitpicks not backed by CLAUDE.md
- Intentional functionality changes
- Generic advice without specifics ("add tests" without saying for what)
- **Issues on lines not changed in this diff** — verified by Scope check above. Common trap: an agent reads `Foo.kt` for context (because the diff calls into it) and then flags pre-existing patterns in `Foo.kt` itself. Drop these.
- **Speculative race conditions** — async-init + sync-read patterns without a quantified non-zero race window.
- **Already-merged "parallel" conflicts** — a referenced commit that's already an ancestor of target.

## Step 6 — Final report

Before writing the report, do a last self-check on every Critical:
- Is the `file:line` actually in the saved diff? (`grep` it if unsure)
- For race-condition findings: is the time-window quantified, and is producer << consumer? If not, downgrade or drop.
- For parallel-work findings: did you confirm the referenced commit is NOT already in target?

A handful of well-grounded Critical findings is better than a long list with pattern-matched speculation. If after filtering only one Critical remains — that's fine, report just that one.

Agent findings already arrive in the resolved language (via the `Language:` prefix from Step 4). Write the report shell — section headers, summary line, recommendation order — in the same resolved language. Code snippets, file paths, identifier names, and CLI commands stay as-is.

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

**Do NOT post to the PR/MR automatically.** Output to the user only — unless `+threads` was passed or the user explicitly asks to post threads (then do Step 7).

## Step 7 — Post inline threads to a GitLab MR (opt-in only)

Only when `+threads` was passed or the user explicitly asks. GitLab MR mode only.

Build a threads JSON from the findings you're posting (blockers + correctness + the test findings worth a thread). Each entry:
- `path` — repo-relative path, exactly as in the diff (`new_path`)
- `line` — line number in the **new** (post-change) file; must be an added or in-hunk line of the diff, else GitLab rejects the position
- `body` — the finding text (markdown; keep it in the resolved report language)

Then post them all as inline, resolvable diff notes with the shipped helper:
```bash
cat > /tmp/threads.json <<'JSON'
[
  {"path": "core/.../Foo.kt", "line": 55, "body": "**Correctness.** ..."},
  {"path": "feature/.../BarTest.kt", "line": 38, "body": "**Test.** ..."}
]
JSON
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post-gitlab-mr-threads.py" \
  --repo <group/project> --mr <iid> --threads /tmp/threads.json
```
The helper reads the MR's `diff_refs` itself and verifies each note came back as a `DiffNote` anchored to `line` (prints `OK`/`ERR` per thread).

**Why the helper, not a raw `glab api` call:** an inline thread needs the position as a **nested JSON `position` object** sent via `glab api --input <file> -H "Content-Type: application/json"`. Passing `-f "position[new_line]=.."` sends flat keys that GitLab silently ignores — you get a plain, non-anchored comment (`type: DiscussionNote`, `position: null`) that looks fine in the API response but isn't attached to any line. The helper encodes the working mechanism so this isn't re-derived each time.

After posting, tell the user how many threads landed and where; do not resolve them yourself.
