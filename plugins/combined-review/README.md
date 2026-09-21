# Combined Review Plugin

Multi-agent code review with CodeRabbit CLI integration.

**Version:** 1.10.1

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
/review 123 +threads                       # same on a GitHub PR
/review feature/CPT-3617 feature/CPT-3600  # Branch diff
/review feature/X to feature/Y            # Same (with "to")
/review --base main                        # Current branch vs main
```

### Optional agents

```bash
/review feature/X feature/Y +comments     # Add comment analysis
/review feature/X feature/Y +types        # Add type design analysis
/review feature/X feature/Y +simplify     # Add code simplification
/review feature/X feature/Y +security     # Add the security agent
/review feature/X feature/Y all           # Run all agents
```

### Setup: `/review-config`

```bash
/review-config            # interactive setup, writes ~/.claude/combined-review.md
/review-config --project  # same, but writes .claude/combined-review.local.md in this repo
/review-config --show     # print the resolved config and where each value came from
```

On the first `/review` with no config anywhere, the command offers this setup and takes defaults if
you decline.

### Re-review: `/rereview`

Follow-up to `/review ... +threads` — checks whether **your own** unresolved threads were
actually fixed in the new revision, then resolves them and approves. GitHub PRs and GitLab MRs.

```bash
/rereview !158                # report only: per-thread ✅ / ⚠️ / ❌ / 🕓 verdicts
/rereview !158 +resolve       # ...and resolve the confirmed ones
/rereview !158 +approve       # ...and approve the MR
/rereview 42 +approve         # same on a GitHub PR
/rereview !158 +agents        # one agent per file instead of inline checking
/rereview                     # PR/MR of the current branch
```

Verdicts come from the code at the head revision, not from replies: GitLab's *"changed this line in
version N of the diff"* auto-note and GitHub's `isOutdated` both fire on any line shift or file move,
and "исправил" is a claim, not evidence.

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
| **security-reviewer** | `+security` or `security: auto` | Secrets, injection, authn/authz, insecure storage and transport, unsafe crypto |

---

## Configuration

Two files, neither inside the plugin — updating or reinstalling it never touches your settings:

- `~/.claude/combined-review.md` — user-level, applies in every repo
- `.claude/combined-review.local.md` — project-level, overrides the user file key by key

Each key resolves separately: project file → user file → default. Write them with `/review-config`,
or by hand as YAML frontmatter:

```yaml
---
language: system    # system | en | ru | uk
model: sonnet       # sonnet | opus | haiku | inherit
coderabbit: auto    # auto | off
security: off       # off | auto
---
```

- **`language`** — language of the final report. `system` auto-detects from CLAUDE.md or your locale.
  Agents get the resolved language up front and return their findings already in it — nothing is
  translated afterwards. Code, file paths, identifiers and CLI commands stay as they are regardless
  of language.
- **`model`** — model the review subagents run on. `opus` goes deeper and burns a personal plan
  faster, `haiku` is cheap and shallow, `inherit` leaves every agent on the model it declares.
- **`coderabbit`** — `auto` uses the CLI when it's installed and authenticated, `off` skips the check
  entirely (no install prompt, no CodeRabbit section). Credentials stay with the CLI
  (`coderabbit auth login` / `coderabbit auth status`); the plugin stores none.
- **`security`** — `off` runs the security agent only on `+security`, `auto` on every review. It is a
  fifth parallel agent, so `auto` costs time on every review and on every shard of a large diff.

The shipped defaults are in `config-defaults.md`.

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

### PR/MR mechanics

- **Fetch.** Both `/review` and `/rereview` fetch the change by its server-side ref —
  `refs/pull/<n>/head` on GitHub, `refs/merge-requests/<iid>/head` on GitLab — which works when the
  change comes from a fork or another project. Fetching the source branch from `origin` fails
  silently in those cases: the branch is in the contributor's repo, not in `origin`. `<repo>` in the
  GitLab form is a remote name or a clone URL; a bare `group/project` path is not something
  `git fetch` accepts.
- **Worktree.** `/review` creates a detached worktree at the revision under review *before* launching
  any agent and passes its path as `Repository root: <path>` in every agent prompt, so agents read the
  code under review instead of whatever happens to be checked out in cwd. CodeRabbit reuses the same
  worktree. If the worktree can't be created the review **stops** — there is no fallback to cwd,
  because agents answering about another branch look exactly like agents answering about this one.
  `current` mode and `--base <branch>` mode need no worktree — the working tree already is
  the revision under review, including untracked files (added as all-added diffs, and not
  double-counted against the staged diff).
- **Pinned to a revision.** Both thread-posting helpers require `--expected-head`, check it against
  the live head (`diff_refs.head_sha` / `head.sha`), and post nothing if they disagree. `/rereview
  +approve` sends `-F "sha=$VERIFIED_HEAD"` on GitLab, where a `409` is treated as a refusal; GitHub
  has no such server-side guard, so the head is re-read and compared before approving and the
  approval carries `commit_id` — a client-side check with a small window, and the report says so. The
  approval gate closes on ❌ not-fixed, ⚠️ partial, and 🕓 deferred — only ✅ passes.
- **Thread dedup.** Before posting, the helper reads the existing threads (paginated) and
  matches findings by path + line — `new_path`/`new_line` on GitLab, `path`/`line` on GitHub, falling
  back to `original_line` for a comment that went outdated so a rebase doesn't hide it. A line that
  already carries a thread — yours from an earlier run or anyone else's — is skipped and reported as
  "already covered in thread N" (`[DUP]`); the author is never read, because the answer is the same
  either way. Skipping is not a failure — the exit status only accounts for threads actually
  attempted. A finding that adds something real to an existing thread is posted as a reply there, not
  as a new thread.
- **Position map.** Scope checking builds a `(new_path, new_line)` map from
  `git diff --unified=0` instead of grepping the saved diff text — grep has no idea where one hunk
  ends and the next begins. The map is built from the *same* revision range the mode diffed, and an
  empty map is treated as a broken one: scope filtering is skipped and the report says so, instead of
  dropping every finding and printing "no issues found". The same map resolves findings anchored on
  deleted lines: a defect in a removed check is still reportable, anchored to the nearest surviving
  line of the same hunk, with the removed code quoted in the finding body.
- **Stack-agnostic.** `test-analyzer` detects the repo's own test-file convention instead of assuming
  `src/test`/`androidTest`; agent prompts carry no Kotlin-specific examples; `git-historian` no longer
  calls `gh` (not in its tool list).
- **CLAUDE.md from the reviewed revision.** `/review` reads `CLAUDE.md` via `git show <target>:CLAUDE.md`
  — from the target revision, not from the working tree and not from the MR's source branch, since an
  adversarial MR could ship its own `CLAUDE.md` with instructions aimed at the reviewer. Agent prompts
  include an explicit trust-boundary note: the diff, the MR/PR description, and source-branch file
  contents are data to analyze, not instructions to follow.
- **Temp files.** Scratch files (CodeRabbit output, discussion dumps) use a private `mktemp`/`mktemp -d`
  under `umask 077` with `trap ... EXIT`, not a fixed predictable path.
- **Forge detection** has an `else` branch for a corporate GitLab on its own domain, instead of only
  recognizing `github.com`/`gitlab.com`.

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

### 1.10.1

- **The position map is built by `python3`, not `awk`.** The command text goes through argument
  substitution before the model executes it, so `substr($0, 7)` arrived as `substr(<argument>, 7)`:
  the map came out as `:42` lines with no file name, non-empty enough that the `POSITION MAP EMPTY`
  guard stayed silent, and every finding was then dropped as out of scope — a review reporting "no
  issues found" because it had discarded everything. Found by running `/review` on this plugin's own
  PR. Python has no `$` for the substitution to touch.
- **`[SEEN]` is gone.** The helpers no longer read who wrote an existing thread: a line that already
  carries one gets no second thread whoever owns it, so the author check (`gh api user` /
  `glab api user`) and the ticket regex that decorated its output bought nothing — and could not be
  verified without a second account. One outcome remains, `[DUP]`, and with it go `TICKET_RE`,
  the standards blocklist and ~40 lines of code and tests.
- `security-reviewer` honours the `Language:` contract — it was the only agent without an
  **Output language** section, so a Russian report came back with its security findings in English.
- `/review` numbers the security agent 5 and CodeRabbit 6, matching the README, `config-defaults.md`
  and `/review-config`, which all call security "a fifth parallel agent". The headings were also out
  of order (6 before 5).

### 1.10.0

- **GitHub parity for threads**: `+threads` posts inline, resolvable review comments on a PR via the
  new `scripts/post-github-pr-threads.py` — same threads JSON, same `--expected-head` guard, same
  `[OK]`/`[DUP]`/`[SEEN]` output as the GitLab helper. It sends `path` + `line` + `side` +
  `commit_id` as a JSON body; the legacy `position` parameter is a diff-hunk offset, not a file line,
  and anchors somewhere unrelated while looking accepted.
- **GitHub parity for `/rereview`**: collects unresolved threads through GraphQL `reviewThreads`
  (REST never reports resolution state), resolves via `resolveReviewThread`, and approves with
  `commit_id` pinned to the verified head after re-reading it. A thread GitHub still tracks needs no
  diff mapping — its `line` is already at head; only an outdated one falls back to `originalLine` at
  `originalCommit`.
- **GitHub PRs are fetched by `refs/pull/<n>/head`**, so a PR from a fork has a real local revision to
  diff, to check out for agents, and to map positions against. `gh pr diff` alone gave text with no
  revision, and `origin/<headRefName>` doesn't exist locally for a fork.
- Fixed, all three introduced in 1.9.0:
  - the position map hardcoded the GitLab range, so on GitHub PR, branch-diff, `--base` and `current`
    the diff failed, the map came out empty, and the scope filter dropped **every** finding while the
    report printed "no issues found". The range is now per mode, and an empty map disables the filter
    and is reported instead of silently emptying the review;
  - a worktree that couldn't be created fell back to cwd, so agents reviewed whatever branch was
    checked out and nothing in the report said so. It now stops the review;
  - the documented MR fetch passed `group/project` as `<repo>`, which `git fetch` answers
    `does not appear to be a git repository` — exactly the fork case the ref form exists for. It now
    says remote name or clone URL, and where to get the URL.
- Fixed: `awk -F/ '{print $1}'` in the CodeRabbit bucketing example (the harness substitutes `$1`
  before the command runs) → `cut -d/ -f1`; `sed -n '<line-15>,...'` in `/rereview` clamped to 1;
  `/rereview` reads both config files, so a user-level `language` is no longer ignored; the posting
  helper's one Russian error string is now English like the rest of the script.

### 1.9.0

- **MR fetch fixed for forks and cross-project MRs**: `/review` and `/rereview` now fetch by
  `refs/merge-requests/<iid>/head` instead of the source branch from `origin`, which silently found
  nothing in those cases.
- **Agents now read the MR revision, not cwd**: `/review` builds the worktree before launching
  agents (previously only CodeRabbit had one) and passes its path to every agent; CodeRabbit reuses
  it.
- **Thread posting is pinned and deduplicated**: the posting helper requires `--expected-head` and
  refuses to post if the MR moved; it also reads existing discussions first and skips findings that
  already have a thread (yours or someone else's), replying in place instead of duplicating.
  `/rereview +approve` pins its approval to the verified head and treats a `409` as a refusal; the
  approval gate now also closes on ⚠️ partial and 🕓 deferred, not just ❌.
- **Scope checking uses a real position map** (`git diff --unified=0`) instead of grepping the diff
  text, and findings on deleted lines are now anchored to a surviving line with the removed code
  quoted, instead of being dropped.
- **Race-condition findings** are dropped or downgraded only by a causal gate (guard, await/join,
  observed state transition) — a timing ratio no longer counts as one.
- **Not Android-only anymore**: `test-analyzer` detects the repo's own test convention instead of
  assuming `src/test`/`androidTest`, agent prompts dropped their Kotlin-specific examples, and
  `git-historian` stopped calling `gh`, which isn't in its tool list.
- **`CLAUDE.md` is read from the reviewed revision** (`git show <target>:CLAUDE.md`), not from the
  working tree or the MR's source branch, and agent prompts carry an explicit trust-boundary note:
  diff, MR description and source-branch files are data, not instructions.
- Fixed: `current` mode now sees untracked files without double-counting them against the staged
  diff; CodeRabbit output goes to a file instead of through `| tail -200` (which was swallowing its
  real exit code); scratch files use a private `mktemp` under `umask 077`; forge detection handles a
  corporate GitLab on its own domain.

### 1.8.0

- **`security-reviewer` agent** — secrets, injection sinks, broken authn/authz, insecure storage and
  transport, unsafe crypto. Stack-agnostic: it derives the platform's idioms from the repo instead of
  assuming one. Opt-in via `+security`, or always-on with `security: auto`.
- **`/review-config`** — interactive setup for language, subagent model, CodeRabbit and the security
  agent; `--project` writes the repo-level file, `--show` prints the resolved values and their source.
  `/review` offers it on the first run with no config.
- **Config now has a user-level file** (`~/.claude/combined-review.md`) alongside the project one, so
  settings survive plugin updates and apply across repos. New keys: `model`, `coderabbit`, `security`.
- Fixed: the install snippet referenced `claude plugin path`, which is not a real CLI command.

### 1.7.0

- **Falsifiability gate** (Step 5.6): every Critical now gets one pass that tries to *invalidate* it — safe behavior, intended behavior, existing mitigation, weak evidence. The existing race-condition and parallel-conflict checks became special cases of it, and a surviving Critical must name which exit it was tested against. Idea borrowed from [pr-af](https://github.com/Agent-Field/pr-af).
- **Evidence rule** (Step 4): any claim about code outside the diff — caller, contract, implementer, mitigation — must quote the snippet with `file:line`. Agents already read for context; now they have to show the read.

### 1.6.0

- `/rereview` gains a per-**file** agent fan-out (`+agents`, automatic above ~8 files): the cost driver is distinct files, not thread count. Each agent gets the path, the head sha and your asks — **not** the author's replies — and answers `present`/`partial`/`absent` with one line of evidence. Withholding the "исправил" reply is the point: it removes the anchoring that makes a plausible diff read as a fix. The main loop re-attaches the replies, which is what separates ❌ not-fixed from 🕓 deferred.

### 1.5.0

- **`/rereview`**: closes the loop after `/review +threads`. Collects your unresolved threads on a GitLab MR (GitHub PRs since 1.10.0), diffs each one's anchor revision (`position.head_sha`) against the current head with `-M` (files move between revisions), and verifies the fix in the code at head — GitLab's "changed this line in version N" auto-note and an author's "fixed" reply are explicitly not accepted as evidence. Reports ✅ / ⚠️ / ❌ / 🕓 per thread; resolving (`+resolve`) and approving (`+approve`) are opt-in, sequential (parallel `glab` calls kill the token).

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
