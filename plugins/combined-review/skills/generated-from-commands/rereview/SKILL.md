---
name: combined-review-rereview
description: Re-review a GitHub PR or GitLab MR: check whether your own unresolved threads were actually fixed in the new revision, then resolve and approve. Use when the user invokes /rereview.
version: 0.1.0
---

> Converted from Claude Code command `/rereview`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Re-review: did they fix my threads?

Follow-up to `/review ... +threads`. Takes **your** unresolved threads on a PR/MR,
verifies against the current head whether each one was actually addressed,
reports per-thread verdicts, and (opt-in) resolves them and approves.

Both forges. The verification (Steps 3–5) is identical; what differs is the API each step calls —
`gh`, including GraphQL for anything about resolution, vs `glab`. Pick the forge exactly as `/review`
Step 1 does: host of `git remote get-url origin`, and on a self-hosted domain the explicit signs in
the repo (`.gitlab-ci.yml` / `gitlab.*` config → GitLab, `.github/` / `gh.*` config → GitHub) — never
a coin flip. `!N` means GitLab explicitly.

## Context

- Directory: !`pwd`
- Branch: !`git branch --show-current 2>/dev/null || echo "detached HEAD"`

## Step 0 — Read config

Same as `/review` Step 0, and the same two files — project first, user second, built-in default last:

```bash
cat .claude/combined-review.local.md 2>/dev/null    # project-level, wins
cat ~/.claude/combined-review.md 2>/dev/null        # user-level, applies everywhere
```

Only `language` matters here (`system` → resolve from CLAUDE.md, else English); the report goes out in
it. Reading just the project file would ignore a user-level `language` and report in the wrong one.

## Arguments

**$ARGUMENTS**

- Mode: `123` (PR or MR on the detected forge), `!123` or a `.../-/merge_requests/123` URL (GitLab
  explicitly), or a `.../pull/123` URL (GitHub explicitly). Empty → the PR/MR of the current branch
  (`gh pr view` / `glab mr view` with no argument).
- `+resolve` — resolve the threads you confirm as fixed, without asking again.
- `+approve` — approve the MR after resolving. Implies `+resolve`.
- `+agents` — force the per-file agent fan-out in Step 4 (it also kicks in on its own above ~8 files).

Without those flags this command is read-only: it reports and asks.

> `!N` is zsh-escaped as `\!N` when typed — the literal mode value is `!N`.
> Run every `glab`/`gh` call from the repo root: both pick the host from the cwd's git remote, and
> outside a repo `glab` silently falls back to gitlab.com and answers `Unauthenticated`.

## Step 1 — Identify the PR/MR and yourself

**GitLab:**
```bash
glab api user                                                    # -> .username (that's "mine")
glab api "projects/<group%2Fproject>/merge_requests/<iid>"       # title, state, source/target, diff_refs
```

Project path = origin, URL-encoded (`my-group%2Fmy-repo`). If the MR lives in another
project, take the path from the URL argument.

**GitHub:**
```bash
gh api user                                                      # -> .login (that's "mine")
gh api "repos/<owner>/<repo>/pulls/<number>"                     # title, state, base/head, head.sha
```

Keep the head SHA — `diff_refs.head_sha` on GitLab, `head.sha` on GitHub. That's the current
revision, the only thing that counts as evidence.

## Step 2 — Collect my unresolved threads

**GitLab:**
```bash
umask 077
DISC_FILE="$(mktemp)"
trap 'rm -f "$DISC_FILE"' EXIT
glab api --paginate "projects/<project>/merge_requests/<iid>/discussions?per_page=100" > "$DISC_FILE"
```

Filter `notes[0]` by:
- `author.username` == your username from Step 1,
- `resolved == false` — **strictly false**. `null`/absent means a plain MR comment that GitLab
  can't resolve at all; count them separately and say so, don't try to resolve them.

For each thread keep: `id`, `position.new_path`, `position.new_line`, `position.head_sha`
(the revision the comment was anchored to), `original_position` (the fallback anchor when
`head_sha` is unreachable — see Step 3), your body, and all replies.

**GitHub:** resolution state lives in GraphQL only — the REST review-comments endpoint never says
whether a thread is resolved, so a REST-based re-review would re-report threads you closed last week.

```bash
umask 077
DISC_FILE="$(mktemp)"
trap 'rm -f "$DISC_FILE"' EXIT
gh api graphql --paginate -F owner="<owner>" -F name="<repo>" -F number=<number> -f query='
query($owner:String!, $name:String!, $number:Int!, $endCursor:String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line originalLine
          comments(first: 50) {
            nodes { author { login } body originalCommit { oid } }
          }
        }
      }
    }
  }
}' > "$DISC_FILE"
```

Filter `nodes` by `isResolved == false` and `comments.nodes[0].author.login` == your login from Step 1.

For each thread keep: `id` (a **node id**, the only thing `resolveReviewThread` accepts — not the REST
comment id), `path`, `line` (the line at the current head; `null` once the thread went outdated),
`originalLine`, `isOutdated`, `comments.nodes[0].originalCommit.oid` (the revision the comment was
anchored to), your body, and all replies.

PR-level comments are a different endpoint (`repos/<owner>/<repo>/issues/<number>/comments`) and are
not resolvable — the GitHub counterpart of GitLab's plain MR comments. Count them separately too.

`--paginate` matters on both: a PR/MR with 100+ threads puts your own unresolved ones on page 2+, and
without it the command silently reviews a partial set and walks right up to approval. On the GraphQL
query it works only because `$endCursor` and `pageInfo` are in the query — drop either and `gh` returns
the first page while looking complete.

## Step 3 — Diff what changed since each comment

**GitHub first, because most threads need no diff at all.** A thread with a non-null `line` is one
GitHub already re-anchored to the current head — take that line and go straight to Step 4. Only an
outdated thread (`isOutdated: true`, `line: null`) needs the mapping below, from `originalLine` at
`originalCommit.oid`.

```bash
git fetch origin "refs/pull/<number>/head:refs/remotes/pr/<number>"
```

`refs/pull/<number>/head` is on **origin** even for a PR from a fork — that's the fetchable ref;
`origin/<headRefName>` doesn't exist locally for a fork. The PR head is then `pr/<number>`.

**GitLab:**
```bash
git fetch "<repo>" "refs/merge-requests/<iid>/head:refs/remotes/mr/<iid>"
```

This form works for an MR from a fork or another project, where `git fetch origin "<source>"`
silently fails — the branch doesn't exist on `origin`. `<repo>` is what `git fetch` accepts as a
remote — a remote name or a clone URL. `origin` for a normal MR; for an MR in another project pass
that project's URL, which `glab api "projects/<group%2Fproject>" --jq .http_url_to_repo` prints. A
bare `group/project` path is **not** a remote: `git fetch "group/project"` answers `does not appear
to be a git repository` and the MR is never fetched.
The MR head is then `mr/<iid>`.

```bash
git diff -M "<anchor_sha>" "<head_sha>"                            # no pathspec — group by anchor
git log --oneline "<anchor_sha>..<head_sha>"
```

`<anchor_sha>` is the revision the comment was made against — `position.head_sha` on GitLab,
`comments.nodes[0].originalCommit.oid` on GitHub. `<head_sha>` is the one from Step 1.

`-M` matters: files often move between revisions (package refactors), which shifts every line
number and renames the path. Run it **without a pathspec** — with a single path on the command
line rename detection doesn't fire, which is the whole reason `-M` is there. Resolve each
thread's new path from the full `git diff --name-status -M` output, then filter to it. Quote
every path and ref substitution (`"Login Flow/Foo.kt"` breaks unquoted).

If `git diff` answers `bad object` for `<anchor_sha>`, that commit is gone — a rebase or
force-push rewrote history after the comment was posted (the normal author reaction to a
review). On GitLab, fall back to `original_position.head_sha` and re-run the diff against that. If
that's missing too — or, on GitHub, if the outdated thread's `originalCommit` is unreachable — the
anchor is unrecoverable: mark it **position lost**, drop it from Step 4's verdicts, and call it out
separately in Step 5's report — don't let it just disappear from the count.

## Step 4 — Verify each thread against the current head

Resolve the thread's line to `<head_sha>` first, unless Step 3 already had it (a GitHub thread with a
non-null `line`): take the new path from Step 3's `git diff --name-status -M` and map the line (from
`position.new_line` / `originalLine`, or from `original_position` if that's what Step 3 fell back to)
through that diff's hunks to the matching line at head — not the raw number from the comment, which
points at a revision that no longer matches. Only then read the code as it is now, not the diff alone:

```bash
git show "<head_sha>:<new_path>" | sed -n '<start>,<head_line+15>p'
```

`<start>` is `head_line - 15` **clamped to 1**: `sed` rejects address `0` and anything negative, so a
finding on one of a file's first 15 lines errors out instead of printing.

**Not evidence of a fix:**
- the auto-note *"changed this line in version N of the diff"* — GitLab posts it on any line shift
  or file move, including a pure package rename with zero logic change;
- a reply saying "исправил" / "fixed" — verify it;
- the thread being outdated (`isOutdated` on GitHub) / the diff position going stale.

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
Threads marked **position lost** in Step 3 don't get a verdict — list them in their own group so
they don't read as silently skipped.

```markdown
## Re-review: <PR #<number> | MR !<iid>> — <title>

Revision <short head_sha> ("<last commit subject>"), <N> commits since my comments.

**Ready to resolve — <n>:**
1. `Foo.kt:431` (onSuccessBioVerification) → `onError = uiState::onDataStateError` ✅

**Leave open — <n>:**
1. `Foo.kt:213` — legacy `networkExecutor {}` still there, no TODO with a ticket.
   Reply: "будет в след. частях" 🕓

**Position lost — <n>:**
1. `Foo.kt` — anchor commit is gone (rebase/force-push), no `original_position` to fall back to.
   Needs a manual look.

<optional: one-line notes on side effects spotted in the new revision>
```

Also mention any of your non-resolvable PR/MR-level comments (Step 2) — they can't be closed via API.

## Step 6 — Resolve (opt-in)

Only with `+resolve`/`+approve` or an explicit go-ahead. **Sequentially**, one call per thread —
parallel `glab`/`gh` calls kill the token:

```bash
# GitLab
glab api -X PUT "projects/<project>/merge_requests/<iid>/discussions/<discussion_id>?resolved=true"

# GitHub - GraphQL only; there is no REST endpoint that resolves a review thread
gh api graphql -F id="<thread node id from Step 2>" -f query='
mutation($id: ID!) {
  resolveReviewThread(input: {threadId: $id}) { thread { id isResolved } }
}'
```

Verify each response — `notes[0].resolved == true` on GitLab,
`data.resolveReviewThread.thread.isResolved == true` on GitHub; report anything that didn't take.

Default to resolving only ✅ threads. Resolve ❌/🕓/⚠️ ones only if the user says "close everything" —
and say plainly in the summary which unfixed threads you closed, so the deferral doesn't get lost.

## Step 7 — Approve (opt-in)

Only with `+approve` or an explicit ask, and only after Step 6:

```bash
# GitLab - the server is the guard
VERIFIED_HEAD="<diff_refs.head_sha from Step 1>"
glab api -X POST "projects/<project>/merge_requests/<iid>/approve" -F "sha=$VERIFIED_HEAD"
```

Pinning `sha` to the head you actually verified makes the server the guard, not your memory:
if the branch moved since Step 1, GitLab answers 409 instead of approving the wrong revision.
Treat 409 as a rejection, not a warning — don't approve, tell the user the branch moved since
you checked, and suggest re-running `/rereview`.

```bash
# GitHub - no server-side guard exists, so check first and pin what you approved
VERIFIED_HEAD="<head.sha from Step 1>"
NOW=$(gh api "repos/<owner>/<repo>/pulls/<number>" --jq .head.sha)
if [ "$NOW" != "$VERIFIED_HEAD" ]; then
  echo "branch moved: verified $VERIFIED_HEAD, now $NOW - not approving"
else
  gh api -X POST "repos/<owner>/<repo>/pulls/<number>/reviews" \
    -f event=APPROVE -f commit_id="$VERIFIED_HEAD"
fi
```

GitHub has no equivalent of GitLab's `sha=`: `commit_id` records **which** commit you approved, it
does not make the API refuse a stale one. So the check is client-side, and a push landing between the
`--jq .head.sha` read and the POST still slips through — a much smaller window than approving off a
Step 1 memory, but not zero. Say that in the report rather than claiming the approval was guarded.
When the check fires, treat it like the 409: don't approve, say the branch moved, suggest re-running.

Report the resulting approvals — `approved_by` on GitLab, the review's `state: APPROVED` on GitHub.
If anything is still ❌ *not fixed*, ⚠️ *partial*, or
🕓 *deferred*, don't approve on your own initiative — say what's open and ask. Only proceed past
an open ❌/⚠️/🕓 thread on the user's explicit go-ahead, same as "close everything" in Step 6 —
and name which unfixed threads you approved over, so the gap doesn't get lost.
