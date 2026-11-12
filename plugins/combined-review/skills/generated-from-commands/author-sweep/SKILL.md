---
name: combined-review-author-sweep
description: Sweep your own open PRs/MRs for unresolved review threads: what needs a fix, what needs a reply, what waits on the reviewer. Use when the user invokes /author-sweep.
version: 0.1.0
---

> Converted from Claude Code command `/author-sweep`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Author sweep: no reviewer thread sits without an answer or a fix

The author-side counterpart of `/review-sweep`: one pass over every open PR/MR of this repository that
you authored, sorting each unresolved review thread by what it needs from you.

Read-only: it pushes nothing and posts nothing unless the user says so (Step 5). It never resolves a
thread on your own PR/MR — whether a fix closes a thread is the reviewer's call.

## Context

- Directory: !`pwd`
- Branch: !`git branch --show-current 2>/dev/null || echo "detached HEAD"`

## Arguments

**$ARGUMENTS**

- `--project <path>` — sweep another project than the one `origin` points at.

## Step 0 — Config

The same two files as `/review` Step 0. Only `language` (the report) and `voice` (drafted replies)
matter here.

## Step 1 — Forge, project, you, your PRs/MRs

Pick the forge as `/review` Step 1 does, and run every call from the repo root.

**GitLab:**
```bash
glab api user --jq .username
glab api --paginate "projects/<group%2Fproject>/merge_requests?state=opened&author_username=<me>&per_page=100"
```
Per MR, the discussions (`--paginate`) and the versions (`.../versions`: `head_commit_sha`, `created_at`).

**GitHub:**
```bash
gh api user --jq .login
gh pr list --state open --author @me --json number,title,isDraft,headRefOid,baseRefName,updatedAt
```
Per PR, the review threads with the GraphQL query of `/rereview` Step 2 (without the author filter).

Keep unresolved threads only. Drop threads opened by bots (GitLab `author.bot`, GitHub author type
`Bot` or a login ending in `[bot]`) — size warnings and pipeline notes are not review; count them in
one line. A PR/MR with no open threads gets one line in the report and no further work.

## Step 2 — Classify each open thread

Let `R` be the reviewer's last human note in the thread and `M` your last human note. A system note
("changed this line in version N") is a signal that the line moved, not a reply.

- **Waiting on the reviewer** — `M` is newer than `R`. Nothing to do; report its age, and flag it
  when it is older than five working days so the user can ping.
- **Reviewer pushed back** — `R` is newer than `M`. Step 3.
- **Unanswered** — no note from you at all. Step 3, to see whether it is also unfixed.

On GitLab, also list the draft notes of an MR with unanswered threads
(`projects/<p>/merge_requests/<iid>/draft_notes`): a draft reply on that discussion means it was
answered but never published — report that instead of drafting a new one.

## Step 3 — Check unanswered and pushed-back threads against the code

Map the thread's line to the current head and read the code there, exactly as `/rereview` Steps 3–4 do.
Never trust a reply text, or a "changed this line" note, alone:
the line can move without the point being addressed. Then check the finding itself — read the class,
helper or caller it refers to at the head. Reviewers are sometimes wrong too.

Verdicts:
- **unanswered and unfixed, the finding holds** → needs a fix: describe it with `path:line`;
- **unanswered and unfixed, the finding is wrong or out of scope** → draft a short reply with the
  reason and the code reference;
- **unanswered, but a later push already fixed it** → draft a reply: fixed in `<sha8>`, and what changed;
- **pushed back** → summarise the reviewer's new argument, say whether it holds, propose a reply or a fix.

## Step 4 — Report

Per PR/MR, in the resolved language: number and title, merge status, number of open threads; then
each thread — reviewer, `path:line`, verdict, and the proposed fix or reply. Name threads by PR/MR,
`path:line` and their point, never by a discussion or node id.

Close with three lists:
- needs a fix — PR/MR and `path:line`;
- needs a reply — with the drafted text;
- waiting on the reviewer — oldest first.

## Step 5 — Act only on the user's word

Push code or post replies only when the user says so, or asked up front to fix and answer.

Fixing:
- work on the PR/MR's source branch; check the branch and `git status` first;
- let the repository's hooks run — a failing hook is fixed, not bypassed;
- new commits only: never amend or squash commits that are already there;
- after the push, reply in each thread you fixed: what changed and where, with the short SHA.

Replying: one reply per thread, into the existing discussion — the conclusion and the code reference,
no account of how you got there. Never resolve a thread on your own PR/MR, even when a merge gate
waits on it.
