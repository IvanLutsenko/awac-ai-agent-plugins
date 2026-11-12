---
description: "Sweep every open PR/MR where you are a reviewer: /review on the untouched ones, /rereview where the author answered or pushed, review of what was pushed since, and one report of what waits on whom."
argument-hint: "[+post] [--project <group/project | owner/repo>]"
allowed-tools: Bash(gh:*), Bash(glab:*), Bash(git:*), Bash(python3:*), Bash(cat:*), Bash(ls:*), Bash(mkdir:*), Bash(cp:*), Bash(date:*), Bash(mktemp:*), Bash(rm:*), Bash(umask:*), Bash(pwd:*), Bash(echo:*), Agent, Read, Write, Glob, Grep
---

# Review sweep: nothing waits on you without a reason

One pass over every open PR/MR of this repository where you are a reviewer. The review itself is not
defined here: a fresh review is `/review`, a thread recheck is `/rereview`. This command decides which
PR/MR needs which, runs them, keeps track of what the previous sweep saw, and reports what waits on whom.

Read-only by default: nothing is posted, resolved or approved. `+post` allows Step 6, and even then
only what the user confirms in this session.

## Context

- Directory: !`pwd`
- Branch: !`git branch --show-current 2>/dev/null || echo "detached HEAD"`

## Arguments

**$ARGUMENTS**

- `+post` — after the report, post what the user confirms (Step 6).
- `--project <path>` — sweep another project than the one `origin` points at.

## Step 0 — Config, procedures, previous sweep

1. Config: the same two files and keys as `/review` Step 0 (`language`, `model`, `rules`, `voice`).
   The report is written in the resolved language; texts meant for threads follow `voice` when set.
2. Load the procedures you will run, so nothing is paraphrased from memory:
   `${CLAUDE_PLUGIN_ROOT}/commands/review.md` and `${CLAUDE_PLUGIN_ROOT}/commands/rereview.md`. If
   either cannot be read, stop and say so — do not improvise a review in their place.
3. Previous sweep: the state directory is
   `${XDG_STATE_HOME:-$HOME/.local/state}/combined-review/sweeps/<host>/<project>/`, where `<project>`
   is the path with `/` replaced by `__`. `latest.md` there is the last report. It records, per PR/MR,
   the head SHA that was reviewed and the findings that were never posted. No directory → first
   sweep, say so in one line.

## Step 1 — Forge, project, you

Pick the forge exactly as `/review` Step 1 does: the host of `git remote get-url origin`, on a
self-hosted domain the signs in the repo — never a coin flip. Run every `glab`/`gh` call from the repo
root: outside it `glab` silently falls back to gitlab.com.

**GitLab:**
```bash
glab api user --jq .username
glab api --paginate "projects/<group%2Fproject>/merge_requests?state=opened&reviewer_username=<me>&per_page=100"
```

**GitHub:** a review request disappears once you have reviewed, so take both lists and merge them.
```bash
gh api user --jq .login
gh pr list --state open --search "review-requested:@me" --json number,title,author,isDraft,headRefOid,baseRefName,updatedAt,labels
gh pr list --state open --search "reviewed-by:@me" --json number,title,author,isDraft,headRefOid,baseRefName,updatedAt,labels
```

PRs/MRs you authored are not part of this sweep — that is `/author-sweep`.

**Already approved, nothing new → skip.** GitLab: `projects/<p>/merge_requests/<iid>/approvals`
lists you in `approved_by`, and no version (`.../versions`) is newer than your approval. GitHub: your
latest review in `pulls/<n>/reviews` is `APPROVED` and its `commit_id` is the current head. An approval
followed by new commits is class C below, whether or not the forge reset it.

## Step 2 — Classify

For every PR/MR left, read its threads — GitLab discussions with `--paginate`, GitHub review threads
with the GraphQL query of `/rereview` Step 2 (without the author filter) — and find yours: threads you
opened, and threads where you replied. System notes ("approved this merge request", "changed this line
in version N") are not threads.

"New code since my last note": GitLab — a version in `.../versions` whose `created_at` is later than
your last note; GitHub — the head differs from the `commit_id` of your latest review or comment.

- **A — no threads of yours, no earlier unposted review** → fresh review (Step 3).
- **A' — no threads of yours, but the previous sweep reviewed it and nothing was posted** → head
  unchanged: reuse those findings as they stand. Head moved: delta review (Step 5) from the head that
  sweep recorded, plus a recheck of those findings at the current head.
- **B — your threads exist, no new code since your last note** → thread recheck only (Step 4).
- **C — your threads exist and there is new code** → thread recheck (Step 4), then delta review (Step 5).

Hold, report the reason, review nothing:
- a draft PR/MR (the forge's draft flag);
- the author asked not to review yet, in a note or the description, in whatever words or language;
- a very large one — hundreds of files, or the base of a chain of PRs/MRs: ask first.

A `WIP`/`Draft` **label** alone is not a hold: review it and mention the label. A trivial change (one
config line, a version bump) needs no five-agent review: read the diff, check the head's pipeline, and
say in the report that it was reviewed inline.

## Step 3 — Fresh review (A)

One subagent per PR/MR, all launched in one message; above ~80 files, one per directory slice. Each
prompt:
- runs `/review` in incoming mode for that PR/MR **without `+threads`** — report only, no forge writes;
- gives number, title, author, target, the head SHA, and for a slice its file scope;
- lists the threads other reviewers already opened (author, `file:line`, one-line gist), so the
  subagent does not repeat them and marks overlaps;
- asks for `/review`'s Step 6 report plus, for every Critical and every finding worth a thread, the
  thread text and its `path:line` anchor valid at that head.

No Agent tool (Codex): run the reviews one after another in this session. Filtering is `/review`'s —
position map, deduplication, falsifiability gate; do not add a confidence score on top.

## Step 4 — Thread recheck (B, C)

Run `/rereview` for the PR/MR, read-only — no `+resolve`, no `+approve`. It maps each of your threads
to the head and judges it by the code there, not by the reply.

**Read every reply in every one of your open threads on every run**, not only the notes since the last
sweep. A reply that arrived between sweeps and was never answered is exactly what a "nothing new"
shortcut misses.

Then, with the replies in view:
- ✅ **fixed** → propose a one-line reply and a resolve.
- **answered, and the answer holds** (checked in the code) → propose a resolve, with a line if it adds
  something.
- **answered, but the answer doesn't hold or misses the point** → draft a short reply: the conclusion
  and the code reference, no essay.
- **answered by another reviewer, not the author** → the user's call: present both positions and a
  proposed reply.
- ❌ **no reply, no change** → waiting on the author; nothing to do.
- **your finding was wrong** → a one-line correction and a resolve. Do not argue it.

Never resolve threads that are not yours.

## Step 5 — Delta review (A', C)

Review only what was pushed after your last review:
- `from` = the head you last reviewed — the newest version older than your last note (GitLab), the
  `commit_id` of your latest review (GitHub), or the head the previous sweep recorded (A'). `to` = the
  current head.
- Diff `from..to`. If the push merged the target branch in, drop the files that came from the target:
  keep only the files the PR/MR itself changes (`git diff --name-only <target>...<to>`).
- Run `/review` as in Step 3 with `<diff-spec>` = `<from>..<to>` restricted to those files: the
  position map is built from the same spec, findings are limited to lines the delta added or changed,
  and anchors are taken at the current head.
- For A', the same subagent rechecks each earlier unposted finding at `to`: still valid (with its
  current line), fixed, or changed.

## Step 6 — Report, then post

Per PR/MR, in the resolved language:
- number, title, class, state;
- findings with `path:line`;
- thread verdicts;
- proposed texts.

Name a thread by its PR/MR, `path:line` and its point — never by a discussion or node id, which the
forge UI does not show.

Close with:
- counts per class;
- what needs the user's decision — disputes, holds;
- approvals to propose: no open threads of yours and no new findings. Other reviewers' open threads do
  not block your approval — they are theirs to close;
- what waits on authors, oldest first.

Save the report as `<YYYY-MM-DD>.md` in the state directory and copy it to `latest.md`, with the
reviewed head SHA and the unposted findings of every PR/MR in it, so the next sweep can start from them.

**Posting** — only with `+post` or the user's explicit go-ahead, and only what they confirm:
- threads go through `/review` Step 7 with `--expected-head` = the head that was reviewed: the helper
  refuses if the branch moved and skips lines that already carry a thread;
- replies go into the existing thread, one per thread;
- resolves and approvals go through `/rereview` `+resolve` / `+approve`, approval pinned to the
  reviewed head. A refused approval because the branch moved means: do not approve.

Findings outside the PR/MR's scope stay in the report. The sweep does not post them.
