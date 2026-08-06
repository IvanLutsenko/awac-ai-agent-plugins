# Combined Review Plugin

Multi-agent code review with CodeRabbit CLI integration.

**Version:** 1.7.0

---

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install combined-review
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add combined-review@awac-ai-agent-plugins
```

Optional (for full functionality):
```bash
# Install CodeRabbit CLI
curl -fsSL https://cli.coderabbit.ai/install.sh | sh

# Authenticate (opens browser)
coderabbit auth login
```

> Without CodeRabbit, the plugin works with 4 agents. CodeRabbit adds a 5th review layer.

---

## Quick Start

```bash
/review                                    # Uncommitted changes
/review 123                                # GitHub PR / GitLab MR by number (forge auto-detected from origin)
/review !22                                # GitLab MR explicitly
/review !22 +threads                       # ...and post findings as inline resolvable MR threads
/review feature/CPT-3617 feature/CPT-3600  # Branch diff
/review feature/X to feature/Y            # Same (with "to")
/review --base main                        # Current branch vs main
```

### Optional agents

```bash
/review feature/X feature/Y +comments     # Add comment analysis
/review feature/X feature/Y +types        # Add type design analysis
/review feature/X feature/Y +simplify     # Add code simplification
/review feature/X feature/Y all           # Run all agents
```

### Re-review: `/rereview`

Follow-up to `/review !22 +threads` — checks whether **your own** unresolved MR threads were
actually fixed in the new revision, then resolves them and approves. GitLab MR only.

```bash
/rereview !158                # report only: per-thread ✅ / ⚠️ / ❌ / 🕓 verdicts
/rereview !158 +resolve       # ...and resolve the confirmed ones
/rereview !158 +approve       # ...and approve the MR
/rereview !158 +agents        # one agent per file instead of inline checking
/rereview                     # MR of the current branch
```

Verdicts come from the code at the MR head, not from replies: GitLab's *"changed this line in
version N of the diff"* auto-note fires on any line shift or file move, and "исправил" is a claim,
not evidence.

---

## Default Agents (5)

| Agent | Focus | Model |
|-------|-------|-------|
| **code-reviewer** | CLAUDE.md compliance, bugs, logic errors, code quality | Sonnet |
| **git-historian** | Git blame, history, reverted fixes, parallel work conflicts | Sonnet |
| **silent-failure-hunter** | Empty catches, swallowed errors, broad exceptions, silent fallbacks | Sonnet |
| **test-analyzer** | Test coverage quality, missing error/edge case tests | Sonnet |
| **CodeRabbit** | AI-powered review via CLI (if installed) | External |

## Optional Agents

| Agent | Trigger | Focus |
|-------|---------|-------|
| Comment Analyzer | `+comments` | Comment accuracy vs code, stale TODOs |
| Type Design Analyzer | `+types` | Encapsulation, invariants, enforcement |
| Code Simplifier | `+simplify` | Simplification without losing functionality |

---

## Configuration

Create `.claude/combined-review.local.md` in your project to customize settings:

```bash
cp $(claude plugin path combined-review)/config-defaults.md .claude/combined-review.local.md
```

Or manually create with YAML frontmatter:

```yaml
---
language: system
---
```

**Language options:**

- `system` — auto-detect from CLAUDE.md or system locale (default)
- `en` — English
- `ru` — Russian
- `uk` — Ukrainian

Agents work internally in English for accuracy; only the final report is output in the configured language.

---

## How It Works

1. **Parse arguments** — determine mode (PR/MR / branch diff / uncommitted)
2. **Gather diff** — via `gh pr diff`, `glab mr` (GitLab), `git diff`, or `git diff branch1...branch2`
3. **Check CodeRabbit** — install if missing (with user consent), check auth
4. **Launch agents in parallel** — 4 default + CodeRabbit + optional
5. **Score and filter** — confidence 0-100, threshold >= 60, deduplicate
6. **Report** — grouped by severity, every finding with `file:line`

### Confidence scoring

- **0-25**: False positive, pre-existing issue
- **25-50**: Possible but unlikely
- **50-75**: Real issue, minor impact
- **75-100**: Confirmed issue, affects functionality

Findings below 60 are filtered out.

### False positive rules

Automatically skipped:
- Pre-existing issues (not in this diff)
- Linter/compiler/CI catches
- Stylistic nitpicks not in CLAUDE.md
- Intentional functionality changes
- Generic advice without specifics

---

## Output Format

Every finding includes file path and line number:

```
## Code Review: feature/X vs feature/Y

**Files:** 12 | **Lines:** +156 / -335 | **Commits:** 1

### Critical

1. `path/to/File.kt:42` — description [source: code-reviewer, confidence: 90]
   > code snippet

### Findings

1. `path/to/File.kt:100` — description [source: silent-failure-hunter, confidence: 75]

### Tests

1. `path/to/File.kt` — missing test for [scenario] [criticality: 8/10]

### CodeRabbit

[Deduplicated results from CodeRabbit CLI]

### Positive

- What's done well
```

---

## Changelog

### 1.7.0

- **Falsifiability gate** (Step 5.6): every Critical now gets one pass that tries to *invalidate* it — safe behavior, intended behavior, existing mitigation, weak evidence. The existing race-condition and parallel-conflict checks became special cases of it, and a surviving Critical must name which exit it was tested against. Idea borrowed from [pr-af](https://github.com/Agent-Field/pr-af).
- **Evidence rule** (Step 4): any claim about code outside the diff — caller, contract, implementer, mitigation — must quote the snippet with `file:line`. Agents already read for context; now they have to show the read.

### 1.6.0

- `/rereview` gains a per-**file** agent fan-out (`+agents`, automatic above ~8 files): the cost driver is distinct files, not thread count. Each agent gets the path, the head sha and your asks — **not** the author's replies — and answers `present`/`partial`/`absent` with one line of evidence. Withholding the "исправил" reply is the point: it removes the anchoring that makes a plausible diff read as a fix. The main loop re-attaches the replies, which is what separates ❌ not-fixed from 🕓 deferred.

### 1.5.0

- **`/rereview`**: closes the loop after `/review +threads`. Collects your unresolved threads on a GitLab MR, diffs each one's anchor revision (`position.head_sha`) against the current head with `-M` (files move between revisions), and verifies the fix in the code at head — GitLab's "changed this line in version N" auto-note and an author's "fixed" reply are explicitly not accepted as evidence. Reports ✅ / ⚠️ / ❌ / 🕓 per thread; resolving (`+resolve`) and approving (`+approve`) are opt-in, sequential (parallel `glab` calls kill the token).

### 1.4.0

- **GitLab MR support**: `/review 123` auto-detects the forge from `origin`; `/review !22` (or an MR URL) targets a GitLab MR via `glab`. Step 2 fetches the MR diff and reads file context from a detached worktree at the MR source branch.
- **`+threads`**: opt-in posting of findings as **inline, resolvable** GitLab MR threads (Step 7), via the shipped `scripts/post-gitlab-mr-threads.py` helper. The helper encodes the only mechanism that anchors a note to a line — a nested `position` JSON via `glab api --input` with `Content-Type: application/json`; `-f "position[...]"` silently produces a non-anchored comment.
- **CodeRabbit CLI ≥ 0.7**: dropped `--plain` (removed upstream; plain is now default and passing it errors). Added a 150-file free-plan guard with a `--dir` bucket-split recipe for large diffs.

### 1.3.0

- **Scope discipline**: agents must not report findings on code outside the diff. Reading-for-context is fine; reporting on unchanged lines is now treated as a false positive in Step 5 filter.
- **Race-condition reality check**: `init { launch { x = suspendRead() } }` + later sync read patterns require a quantified producer/consumer time-window. Pattern-based race claims without timing are dropped.
- **Parallel-conflict verification**: git-historian must confirm referenced commits are NOT already in target via `git merge-base --is-ancestor` before flagging.
- Step 6 adds an explicit pre-write self-check on every Critical finding.

### 1.2.0

- (Internal: version bumped without changelog entry)

### 1.1.0

- Language configuration: system (auto-detect), en, ru, uk
- Config file support: `.claude/combined-review.local.md`

### 1.0.0

- Initial release
- 4 default agents: code-reviewer, git-historian, silent-failure-hunter, test-analyzer
- CodeRabbit CLI integration with auto-install
- Support for PR, branch diff, and uncommitted changes
- Confidence scoring and false positive filtering
- Optional agents: +comments, +types, +simplify

---

## License

MIT
