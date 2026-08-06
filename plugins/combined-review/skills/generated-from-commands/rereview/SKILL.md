---
name: combined-review-rereview
description: Re-review a GitLab MR: check whether your own unresolved threads were actually fixed in the new revision, then resolve and approve. Use when the user invokes /rereview.
version: 0.1.0
---

> Converted from Claude Code command `/rereview`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Re-review: did they fix my threads?

Follow-up to `/review ... +threads`. Takes **your** unresolved threads on an MR,
verifies against the current head whether each one was actually addressed,
reports per-thread verdicts, and (opt-in) resolves them and approves.

GitLab MR only — GitHub review threads need a different (GraphQL) resolve path.

## Context

- Directory: !`pwd`
- Branch: !`git branch --show-current 2>/dev/null || echo "detached HEAD"`

## Step 0 — Read config

Same as `/review`: read `language` from `.claude/combined-review.local.md` frontmatter
(default `system` → resolve from CLAUDE.md, else English). The report goes out in that language.

## Arguments

**$ARGUMENTS**

- Mode: `!123`, `123`, or a `.../-/merge_requests/123` URL. Empty → the MR of the current branch
  (`glab mr view` with no argument).
- `+resolve` — resolve the threads you confirm as fixed, without asking again.
- `+approve` — approve the MR after resolving. Implies `+resolve`.
- `+agents` — force the per-file agent fan-out in Step 4 (it also kicks in on its own above ~8 files).

Without those flags this command is read-only: it reports and asks.

> `!N` is zsh-escaped as `\!N` when typed — the literal mode value is `!N`.
> Run every `glab` call from the repo root: `glab` picks the host from the cwd's git remote,
> and outside a repo it silently falls back to gitlab.com and answers `Unauthenticated`.

## Step 1 — Identify the MR and yourself

```bash
glab api user                                                    # -> .username (that's "mine")
glab api "projects/<group%2Fproject>/merge_requests/<iid>"       # title, state, source/target, diff_refs
```

Project path = origin, URL-encoded (`bbusiness%2Fandroid-app`). If the MR lives in another
project, take the path from the URL argument.

Keep `diff_refs.head_sha` — that's the current revision, the only thing that counts as evidence.

## Step 2 — Collect my unresolved threads

```bash
glab api "projects/<project>/merge_requests/<iid>/discussions?per_page=100" > /tmp/mr<iid>_disc.json
```

Filter `notes[0]` by:
- `author.username` == your username from Step 1,
- `resolved == false` — **strictly false**. `null`/absent means a plain MR comment that GitLab
  can't resolve at all; count them separately and say so, don't try to resolve them.

For each thread keep: `id`, `position.new_path`, `position.new_line`, `position.head_sha`
(the revision the comment was anchored to), your body, and all replies.

## Step 3 — Diff what changed since each comment

```bash
git fetch origin <source_branch>
git diff -M <position.head_sha> <diff_refs.head_sha> -- <path>      # per thread (group by head_sha)
git log --oneline <position.head_sha>..<diff_refs.head_sha>
```

`-M` matters: files often move between revisions (package refactors), which shifts every line
number and renames the path. Resolve the new path from `git diff --name-status -M` before reading.

## Step 4 — Verify each thread against the current head

Read the code as it is now, not the diff alone:

```bash
git show <diff_refs.head_sha>:<new_path> | sed -n '<line-15>,<line+15>p'
```

**Not evidence of a fix:**
- the auto-note *"changed this line in version N of the diff"* — GitLab posts it on any line shift
  or file move, including a pure package rename with zero logic change;
- a reply saying "исправил" / "fixed" — verify it;
- the thread being outdated / the diff position going stale.

**Evidence:** the requested change is present in the file at `head_sha`, and it compiles as written
(e.g. if you asked to drop `orZero()`, check the target field is actually nullable).

### Inline or fan out

Do it inline. The cost driver is **distinct files**, not thread count — five threads in one file is
one read. Fan out one agent **per file** (not per thread) when the threads span more than ~8 files,
or when `+agents` was passed.

Each agent gets: the file path, `head_sha`, and the *asks* — your original thread bodies and their
line numbers. **Do not pass the author's replies.** The agent answers, per thread, only
`present` / `partial` / `absent` plus one line of evidence from the code. Keeping the "исправил"
reply out of its context is the point: it removes the anchoring that makes a plausible-looking
diff read as a fix.

The main loop then maps those verdicts to the four below, using the replies it kept — a reply is
what separates ❌ *not fixed* from 🕓 *deferred*, and it never turns `absent` into ✅.

Verdict per thread:
- ✅ **fixed** — change is in the code at head.
- ⚠️ **partial** — some of the ask landed; name what's missing.
- ❌ **not fixed** — no matching change; the reply, if any, doesn't claim one either.
- 🕓 **deferred** — author explicitly declined/postponed with a reason ("следующим MR"). Not a fix;
  the user decides whether that's acceptable. If the ask was "fix it or leave a marker", check
  whether the marker (TODO with ticket) is in the code — usually it isn't.

## Step 5 — Report

Group by verdict, most actionable first. Cite `new_path:new_line` **at head**, not the stale
position from the comment. One line of evidence per thread — the applied hunk or its absence.

```markdown
## Re-review: MR !<iid> — <title>

Revision <short head_sha> ("<last commit subject>"), <N> commits since my comments.

**Ready to resolve — <n>:**
1. `Foo.kt:431` (onSuccessBioVerification) → `onError = uiState::onDataStateError` ✅

**Leave open — <n>:**
1. `Foo.kt:213` — legacy `networkExecutor {}` still there, no TODO with a ticket.
   Reply: "будет в след. частях" 🕓

<optional: one-line notes on side effects spotted in the new revision>
```

Also mention any of your non-resolvable MR-level comments (Step 2) — they can't be closed via API.

## Step 6 — Resolve (opt-in)

Only with `+resolve`/`+approve` or an explicit go-ahead. **Sequentially**, one call per thread —
parallel `glab` calls kill the token:

```bash
glab api -X PUT "projects/<project>/merge_requests/<iid>/discussions/<discussion_id>?resolved=true"
```

Verify each response has `notes[0].resolved == true`; report anything that didn't take.

Default to resolving only ✅ threads. Resolve ❌/🕓/⚠️ ones only if the user says "close everything" —
and say plainly in the summary which unfixed threads you closed, so the deferral doesn't get lost.

## Step 7 — Approve (opt-in)

Only with `+approve` or an explicit ask, and only after Step 6:

```bash
glab api -X POST "projects/<project>/merge_requests/<iid>/approve"
```

Report the resulting `approved_by` list. If anything is still ❌, don't approve on your own
initiative — say what's open and ask.
