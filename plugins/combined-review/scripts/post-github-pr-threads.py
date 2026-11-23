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
                    An entry with both `line` and `old_line`, or with neither,
                    stops the run before anything is posted. So does an entry that
                    is not an object, a `path` or `body` that is not a non-empty string,
                    or a line number that is not a positive integer.
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
import argparse, json, subprocess, sys, tempfile, os, re


ZWSP = "\u200b"
# Only a closed fence is exempt; an unclosed one stays prose. Errors here must fall to the safe side.
_FENCE = re.compile(r"(^ {0,3}(?:```[^`\n]*\n.*?^ {0,3}```|~~~[^\n]*\n.*?^ {0,3}~~~)[ \t]*$)", re.M | re.S)
# one line only (a stray backtick must not swallow paragraphs); runs match whole, as in CommonMark
_INLINE = re.compile(r"(?<!`)(`+)(?!`)([^\n]+?)(?<!`)\1(?!`)")


def neutralize(body):
    """Defuse text an agent may have copied from the diff or MR before it is posted as you.

    A line starting with `/` is a GitLab quick action (`/merge`, `/approve`, `/assign`) run with
    the poster's rights; `@name` pings people. Both get a zero-width space after the trigger
    character. Fenced blocks and inline code are left byte-exact: quick actions and mentions
    don't fire there, and a snippet must stay copy-pasteable.
    """
    def prose(t):
        t = re.sub(r"^(\s*)/", r"\1/" + ZWSP, t, flags=re.M)  # before inline split: line starts only
        parts = _INLINE.split(t)  # [text, ticks, code, text, ...]
        for i in range(0, len(parts), 3):
            parts[i] = re.sub(r"@(?=[\w-])", "@" + ZWSP, parts[i])
        out, i = [], 0
        while i < len(parts):
            out.append(parts[i])
            if i + 2 < len(parts):
                out.append(parts[i + 1] + parts[i + 2] + parts[i + 1])
            i += 3
        return "".join(out)
    chunks = _FENCE.split(body)  # odd indexes are fenced blocks
    return "".join(c if i % 2 else prose(c) for i, c in enumerate(chunks))


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


def line_number(t, key):
    """`t[key]` as a line number. JSON `true` is a Python bool, which is an int,
    so `type(...) is int` is the check: `line: true` must not post on line 1."""
    x = t[key]
    if type(x) is not int or x < 1:
        raise ValueError(f"`{key}` must be a positive integer, got {x!r}")
    return x


def anchor_of(t):
    """("RIGHT", line) for a thread entry, or ("LEFT", old_line) for a removed line.
    Raises ValueError for an entry with both `line` and `old_line`, or with neither."""
    if t.get("old_line") is not None:
        if t.get("line") is not None:
            raise ValueError("a thread takes `line` or `old_line`, not both")
        return "LEFT", line_number(t, "old_line")
    if t.get("line") is None:
        raise ValueError("a thread needs `line` or `old_line`")
    return "RIGHT", line_number(t, "line")


def resolve_anchors(threads):
    """Anchors of all entries, in order. Exits on the first malformed one, so a bad
    entry stops the run before anything is posted, not halfway through it: every
    field the posting loop reads is checked here."""
    if not isinstance(threads, list):
        sys.exit(f"threads file must hold a JSON list, got {type(threads).__name__} - nothing posted")
    anchors = []
    for i, t in enumerate(threads, 1):
        label = "<no path>"
        try:
            if not isinstance(t, dict):
                raise ValueError(f"an entry must be an object, got {type(t).__name__}")
            path = t.get("path")
            if not isinstance(path, str) or not path:
                raise ValueError("a thread needs `path` as a non-empty string")
            label = path
            body = t.get("body")
            if not isinstance(body, str) or not body.strip():
                raise ValueError("a thread needs `body` as a non-empty string")
            anchors.append(anchor_of(t))
        except (ValueError, TypeError) as e:
            sys.exit(f"threads[{i}] {label}: {e} - nothing posted")
    return anchors


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
    anchors = resolve_anchors(threads)
    head_sha = get_head_sha(a.repo, a.pr)

    if head_sha != a.expected_head:
        sys.exit(
            f"branch moved: analyzed {a.expected_head}, now {head_sha}"
        )

    comments = get_review_comments(a.repo, a.pr)

    ok = tried = skipped = 0
    for t, (side, line) in zip(threads, anchors):
        path = t["path"]
        short = f"{path.split('/')[-1]}:{line}" + (" (removed)" if side == "LEFT" else "")
        outcome, cid = match_thread(comments, path, line, side)
        if outcome == "dup":
            skipped += 1
            print(f"[DUP] {short} -> thread {cid} already on that line, not posted")
            continue
        tried += 1
        good, msg = post_thread(a.repo, a.pr, head_sha, path, line, neutralize(t["body"]), side)
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
