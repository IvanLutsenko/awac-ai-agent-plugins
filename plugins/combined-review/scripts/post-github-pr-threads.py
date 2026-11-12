#!/usr/bin/env python3
"""Post inline, resolvable review threads to a GitHub PR as diff-anchored comments.

The GitHub counterpart of post-gitlab-mr-threads.py, same contract, same output.

Encodes the ONE mechanism that anchors a comment to a line of a file:
`POST /repos/{owner}/{repo}/pulls/{n}/comments` with a JSON body carrying
`path` + `line` + `side` + `commit_id`, sent via `gh api --input`.

Do NOT use the legacy `position` parameter: it is an offset *inside the diff
hunk*, not a line of the file, so a finding's file line number posted as
`position` lands on an unrelated line (or 422s) while looking accepted.
Do NOT use `gh api -f line=42` either: `-f` always sends a string and the API
wants an integer — hence the JSON body file.

Usage:
    post-github-pr-threads.py --repo <owner/repo> --pr <number> --threads <file.json> \
        --expected-head <sha>

  --repo           "owner/repo"
  --pr             PR number
  --threads        JSON file: [{"path": "...", "line": 42, "body": "..."}, ...]
                    `line` is the line number in the NEW (post-change) file; it must be
                    an added or in-hunk line of the PR diff, or GitHub rejects it.
                    A finding on a line the PR removed carries `old_line` instead of
                    `line`: its number in the OLD (pre-change) file, posted on the LEFT
                    side. `old_path` is accepted for parity with GitLab and ignored: a
                    review comment names the file by its path in the PR on either side.
  --expected-head  SHA the findings were analyzed against. Required: compared against
                    the PR's live head.sha before posting anything; if the branch moved
                    since analysis, nothing is posted and the script exits non-zero.
                    That SHA is also the comments' `commit_id`.

Before posting, reads the PR's existing review comments and skips findings whose
`path` + `line` + side already carry a thread — anyone's: `[DUP]`. Whose it is does not
change what to do (never pile a second thread onto a discussed line), so the author
is not read at all. A skip is not a failure — exit code is non-zero only if a thread
that was actually attempted failed to anchor.
"""
import argparse, json, subprocess, sys, tempfile, os


def gh_api(path, method=None, headers=None, input_file=None, paginate=False):
    args = ["gh", "api", path]
    if method:
        args += ["-X", method]
    if paginate:
        args += ["--paginate"]
    for h in headers or []:
        args += ["-H", h]
    if input_file:
        args += ["--input", input_file]
    r = subprocess.run(args, capture_output=True, text=True)
    if paginate and r.returncode != 0:
        # `gh api --paginate` streams one page at a time. A failure on page 2+
        # (rate limit, dropped connection, expired token) leaves the earlier pages
        # on stdout as valid JSON, so the caller would decode a partial list and
        # treat it as the complete one - and post duplicates against it.
        sys.exit(
            f"`gh api --paginate {path}` failed (exit {r.returncode}) after "
            f"{len(r.stdout)} bytes: {(r.stderr or r.stdout)[:300]}"
        )
    return r.stdout, r.stderr


def decode_pages(out):
    """`gh api --paginate` prints one JSON array per page, concatenated. Decode them in turn."""
    dec, items, i = json.JSONDecoder(), [], 0
    while i < len(out):
        page, i = dec.raw_decode(out, i)
        items += page
        while i < len(out) and out[i].isspace():
            i += 1
    return items


def get_head_sha(repo, pr):
    out, err = gh_api(f"repos/{repo}/pulls/{pr}")
    try:
        return json.loads(out)["head"]["sha"]
    except Exception:
        sys.exit(f"cannot read head.sha for {repo}#{pr}: {(out + err)[:300]}")


def get_review_comments(repo, pr):
    """All review comments of the PR. `--paginate` matters: a PR with 100+ comments
    hides the older ones on page 2+, and a partial read posts duplicates."""
    out, err = gh_api(
        f"repos/{repo}/pulls/{pr}/comments?per_page=100", paginate=True
    )
    # A failed `gh` call leaves stdout empty; a PR with no comments still returns `[]`.
    # Without this the decode loop below never runs, returns [], and dedup silently turns off.
    if not out.strip():
        sys.exit(f"cannot read review comments for {repo}#{pr}: {err[:300] or 'empty response'}")
    try:
        return decode_pages(out)
    except Exception:
        sys.exit(f"cannot read review comments for {repo}#{pr}: {(out + err)[:300]}")


def anchor_of(t):
    """("RIGHT", line) for a thread entry, or ("LEFT", old_line) for a removed line.
    An entry with both `line` and `old_line` is refused."""
    if t.get("old_line") is not None:
        if t.get("line") is not None:
            sys.exit(f"{t['path']}: a thread takes `line` or `old_line`, not both")
        return "LEFT", int(t["old_line"])
    return "RIGHT", int(t["line"])


def match_thread(comments, path, line, side="RIGHT"):
    """Is this finding's line already covered by an existing thread?

    Match is on the thread-starting comment's `path` + `line` on the same side.
    A reply (`in_reply_to_id` set) is part of a thread that already matched on its
    own root, so replies are skipped. So is a comment on the other side: a LEFT
    line of that number is the pre-change line, a different place in the file from
    the RIGHT-side line of the same number. An outdated comment reports `line: null` and
    keeps the anchor in `original_line` — match on that, otherwise a rebase makes
    every earlier thread invisible and the next run posts them all again.

    Returns (outcome, comment_id):
      ("post", None)   - nothing there, post it
      ("dup", <id>)    - a thread is already on that line; skip and name it
    """
    for c in comments:
        if c.get("in_reply_to_id"):
            continue
        if (c.get("side") or "RIGHT") != side:
            continue
        anchor = c.get("line")
        if anchor is None:
            anchor = c.get("original_line")
        if c.get("path") != path or anchor != line:
            continue
        return "dup", c.get("id")
    return "post", None


def post_thread(repo, pr, head_sha, path, line, body, side="RIGHT"):
    payload = {
        "body": body,
        "commit_id": head_sha,
        "path": path,
        "line": line,
        "side": side,
    }
    fd, fn = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps(payload).encode())
    os.close(fd)
    try:
        out, err = gh_api(
            f"repos/{repo}/pulls/{pr}/comments",
            method="POST",
            headers=["Content-Type: application/json"],
            input_file=fn,
        )
    finally:
        os.unlink(fn)
    try:
        c = json.loads(out)
        ok = (
            c.get("path") == path
            and c.get("line") == line
            and (c.get("side") or "RIGHT") == side
        )
        return ok, f"{c['id']} path={c.get('path')} line={c.get('line')} side={c.get('side')}"
    except Exception:
        return False, (out + err)[:300]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--threads", required=True)
    ap.add_argument("--expected-head", required=True)
    a = ap.parse_args()

    threads = json.load(open(a.threads))
    head_sha = get_head_sha(a.repo, a.pr)

    if head_sha != a.expected_head:
        sys.exit(
            f"branch moved: analyzed {a.expected_head}, now {head_sha}"
        )

    comments = get_review_comments(a.repo, a.pr)

    ok = tried = skipped = 0
    for t in threads:
        side, line = anchor_of(t)
        path = t["path"]
        short = f"{path.split('/')[-1]}:{line}" + (" (removed)" if side == "LEFT" else "")
        outcome, cid = match_thread(comments, path, line, side)
        if outcome == "dup":
            skipped += 1
            print(f"[DUP] {short} -> thread {cid} already on that line, not posted")
            continue
        tried += 1
        good, msg = post_thread(a.repo, a.pr, head_sha, path, line, t["body"], side)
        print(f"[{'OK ' if good else 'ERR'}] {short} -> {msg}")
        ok += 1 if good else 0
    print(f"--- {ok}/{tried} inline threads posted, {skipped} skipped as already covered ---")

    # The guard above runs once, before the loop. A push landing while we post
    # still gets the comments - GitHub accepts a non-latest `commit_id` and just
    # marks them outdated, so every one of them came back [OK]. Say so instead of
    # reporting a clean run: the threads are anchored to a revision nobody reviews
    # any more. Checking once here costs one request; checking per thread doubles
    # the whole run for a window of seconds.
    if tried and get_head_sha(a.repo, a.pr) != head_sha:
        sys.exit(
            f"branch moved while posting: the {tried} thread(s) above are anchored to "
            f"{head_sha}, which is no longer the head - re-run the review"
        )
    sys.exit(0 if ok == tried else 1)


if __name__ == "__main__":
    main()
