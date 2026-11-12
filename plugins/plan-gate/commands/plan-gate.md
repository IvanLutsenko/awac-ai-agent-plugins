---
description: "Plan, approve, execute, verify: the plan is written and shown first, nothing changes until a person approves it, a cheaper executor agent carries it out, and the diff is reviewed against the plan before the report."
argument-hint: "<task text | path to a spec> [--resume <plan file>]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git:*), Bash(ls:*), Bash(cat:*), Bash(mkdir:*), Bash(date:*), Agent, AskUserQuestion
---

# Plan gate

Planning and review need the strongest model; carrying out a plan that is already precise does not.
This command splits the work that way, with a person between the two halves: the plan is written and
shown, **nothing in the repository changes until the person approves it**, then the `executor` agent
carries it out on a cheaper model, and the result is checked against the plan before anyone is told
it is done.

The tracker does not matter: the input is the task's text — pasted from a ticket, typed, or a path to
a spec.

## Context

- Directory: !`pwd`
- Branch: !`git branch --show-current 2>/dev/null || echo "detached HEAD"`
- Uncommitted changes: !`git status --porcelain 2>/dev/null | head -5`

## Arguments

**$ARGUMENTS**

- the task, or a path to a file that holds it;
- `--resume <plan file>` — continue from the gate with a plan written earlier.

## Step 0 — Config

```bash
cat .claude/plan-gate.local.md 2>/dev/null    # project-level, wins
cat ~/.claude/plan-gate.md 2>/dev/null        # user-level
```

Keys and defaults: `${CLAUDE_PLUGIN_ROOT}/config-defaults.md` — `executor_model`, `review`,
`max_change`, `verify`.

Uncommitted changes in the working tree are not yours: say so and ask before planning on top of them.

## Step 1 — Gather, change nothing

- the task text, and anything it links that you can read;
- the repo policy files — `CLAUDE.md`, `AGENTS.md`, root and the directories the task touches;
- the code the task touches: find it, read it in full, and find the closest existing example of the
  same kind of change in the repository — the plan follows the repository's patterns, not generic ones;
- the tests next to that code, and how the repository runs them.

What you cannot find out from the repository goes into the plan as an open question, not a guess.

## Step 2 — Write the plan

Write it to `${XDG_STATE_HOME:-$HOME/.local/state}/plan-gate/<repo>/<YYYY-MM-DD>-<slug>.md` — outside the
repository, so it never shows up in a diff — with these sections:

1. **Goal** — one or two sentences: what is true when this is done.
2. **Scope** — in, and explicitly out.
3. **Steps** — numbered; each names the files it touches and what changes in them, specific enough
   that the executor makes no design decision. New files are named here too.
4. **Tests** — which tests are added or changed, and what each one proves.
5. **Verify** — the exact commands that show it works (`verify` from the config when set).
6. **Slicing** — when `max_change` is set and the estimate exceeds it: how the work splits into
   consecutive changes, each with its own estimate, each one buildable on its own.
7. **Do not** — what the executor must not touch: files outside the steps, dependencies, public
   APIs not named in the steps, unrelated refactoring.
8. **Open questions** — what the person has to decide.

## Step 3 — The gate

Show the plan and stop. Ask the person to approve it, change it, or stop. Only an explicit approval
moves on: silence, "looks fine?", or an answer to one open question is not one. A change → revise the
plan file, show what changed in it, and ask again.

**In a non-interactive run** (`codex exec`, CI, nobody to ask): stop after the plan and print its
path. Never execute an unapproved plan.

## Step 4 — Execute

Launch the `executor` agent with: the plan file's path, the repository root, the approved steps (all,
or one slice), and the policy files. Model: `executor_model` (`sonnet` by default). Independent slices
that touch disjoint files may run in parallel; anything else runs in order.

The executor reports per step: done or stopped, files changed, commands run and their result, and every
deviation. A stopped step comes back to you, not to a retry: decide whether the plan was wrong (revise
it and go through the gate again for that part) or the executor misread it (send it back with the
clarification).

No Agent tool (Codex): carry out the approved steps yourself in this session, holding to the plan
exactly as the executor would — the gate has already happened.

## Step 5 — Verify against the plan

1. Run the plan's **Verify** commands yourself and read their output; a summary line is not evidence.
2. Review the diff:
   - `review: auto` (default) — with the `combined-review` plugin installed, run `/review` on the
     uncommitted work (or the branch); without it, review inline;
   - `review: inline` — always inline.
   Inline means: every step of the plan is in the diff, nothing outside the plan is, the tests prove
   what the plan says they prove, and no debug output or commented-out code is left behind.
3. Findings go back to the executor as a numbered fix list. At most two rounds; whatever is left after
   that goes into the report instead of a third round.

## Step 6 — Report

- each plan step: done / changed / not done, with the files;
- verification commands and their results;
- review findings and what became of them;
- deviations from the plan, and why;
- what is left for the person. Committing, pushing and opening a PR/MR are theirs unless the plan says
  otherwise.
