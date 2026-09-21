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
  --expected-head  SHA the findings were analyzed against. Required: compared against
                    the PR's live head.sha before posting anything; if the branch moved
                    since analysis, nothing is posted and the script exits non-zero.
                    That SHA is also the comments' `commit_id`.

Before posting, reads the PR's existing review comments and skips findings whose
`path` + `line` already carry a thread: `[DUP]` for one of your own from a previous
run, `[SEEN]` for someone else's. A skip is not a failure — exit code is non-zero
only if a thread that was actually attempted failed to anchor.
"""
import argparse, json, re, subprocess, sys, tempfile, os


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


def get_login():
    out, err = gh_api("user")
    try:
        return json.loads(out)["login"]
    except Exception:
        sys.exit(f"cannot read current user from `gh api user`: {(out + err)[:300]}")


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


TICKET_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
# ponytail: prefix blocklist, not a project-key lookup — these standards read exactly like keys
NOT_TICKET = {"UTF", "SHA", "AES", "RSA", "MD", "ISO", "RFC", "TLS", "HMAC", "PBKDF", "BASE", "IPV", "X"}


def find_ticket(body):
    """First ticket key in the text; a standard that looks like one (UTF-8, SHA-256) is not a ticket."""
    for m in TICKET_RE.finditer(body or ""):
        if m.group(0).split("-")[0] not in NOT_TICKET:
            return m.group(0)
    return None


def match_thread(comments, path, line, me):
    """Is this finding's line already covered by an existing thread?

    Match is on the thread-starting comment's `path` + `line` on the RIGHT side.
    A reply (`in_reply_to_id` set) is part of a thread that already matched on its
    own root, so replies are skipped. So is a LEFT-side comment: it sits on the
    pre-change line of that number, which is a different place in the file from
    the RIGHT-side line `post_thread` posts to. An outdated comment reports `line: null` and
    keeps the anchor in `original_line` — match on that, otherwise a rebase makes
    every earlier thread invisible and the next run posts them all again.

    Returns (outcome, comment_id, ticket):
      ("post", None, None)          - nothing there, post it
      ("mine", <id>, None)          - my own thread from a previous run
      ("theirs", <id>, <ticket>)    - someone else's thread; ticket if one is mentioned
    """
    threads = {}
    for c in comments:
        root = c.get("in_reply_to_id") or c.get("id")
        threads.setdefault(root, []).append(c)
    for c in comments:
        if c.get("in_reply_to_id"):
            continue
        if (c.get("side") or "RIGHT") != "RIGHT":
            continue
        anchor = c.get("line")
        if anchor is None:
            anchor = c.get("original_line")
        if c.get("path") != path or anchor != line:
            continue
        if (c.get("user") or {}).get("login") == me:
            return "mine", c.get("id"), None
        for n in threads.get(c.get("id"), [c]):
            t = find_ticket(n.get("body"))
            if t:
                return "theirs", c.get("id"), t
        return "theirs", c.get("id"), None
    return "post", None, None


def post_thread(repo, pr, head_sha, path, line, body):
    payload = {
        "body": body,
        "commit_id": head_sha,
        "path": path,
        "line": line,
        "side": "RIGHT",
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
        ok = c.get("path") == path and c.get("line") == line
        return ok, f"{c['id']} path={c.get('path')} line={c.get('line')}"
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

    me = get_login()
    comments = get_review_comments(a.repo, a.pr)

    ok = tried = skipped = 0
    for t in threads:
        path, line = t["path"], int(t["line"])
        short = f"{path.split('/')[-1]}:{line}"
        outcome, cid, ticket = match_thread(comments, path, line, me)
        if outcome == "mine":
            skipped += 1
            print(f"[DUP] {short} -> own thread {cid}, not posted")
            continue
        if outcome == "theirs":
            skipped += 1
            tk = f" ticket={ticket}" if ticket else ""
            print(f"[SEEN] {short} -> thread {cid}{tk}, not posted")
            continue
        tried += 1
        good, msg = post_thread(a.repo, a.pr, head_sha, path, line, t["body"])
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
