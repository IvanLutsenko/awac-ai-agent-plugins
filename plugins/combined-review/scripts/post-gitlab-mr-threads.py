#!/usr/bin/env python3
"""Post inline, resolvable review threads to a GitLab MR as diff-anchored notes.

Encodes the ONE mechanism that actually anchors a note to a line:
a JSON body with a nested `position` object sent via `glab api --input`
with an explicit `Content-Type: application/json` header.

Do NOT use `glab api -f "position[new_line]=.."`: the bracket keys are sent
as flat JSON keys, GitLab ignores them, and you silently get a plain
(non-anchored) comment instead of an inline thread.

Usage:
    post-gitlab-mr-threads.py --repo <path-or-id> --mr <iid> --threads <file.json> \
        --expected-head <sha>

  --repo           "group/project" (URL-encoded automatically) or numeric project id
  --mr             MR iid (the !N number)
  --threads        JSON file: [{"path": "...", "line": 42, "body": "..."}, ...]
                    `line` is the line number in the NEW (post-change) file; it must be
                    an added or in-hunk line of the MR diff, or GitLab rejects it.
  --expected-head  SHA the findings were analyzed against. Required: compared against
                    the MR's live diff_refs.head_sha before posting anything; if the
                    branch moved since analysis, nothing is posted and the script exits
                    non-zero.

Reads diff_refs from the MR itself, so the caller only supplies findings.

Before posting, reads the MR's existing discussions and skips findings whose
`new_path` + `new_line` already carry a thread: `[DUP]` for one of your own from
a previous run, `[SEEN]` for someone else's. A skip is not a failure — exit code
is non-zero only if a thread that was actually attempted failed to anchor.
"""
import argparse, json, re, subprocess, sys, tempfile, os
from urllib.parse import quote


def glab_api(path, method=None, headers=None, input_file=None, paginate=False):
    args = ["glab", "api", path]
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
        # `glab api --paginate` streams one page at a time. A failure on page 2+
        # (rate limit, dropped connection, expired token) leaves the earlier pages
        # on stdout as valid JSON, so the caller would decode a partial list and
        # treat it as the complete one - and post duplicates against it.
        sys.exit(
            f"`glab api --paginate {path}` failed (exit {r.returncode}) after "
            f"{len(r.stdout)} bytes: {(r.stderr or r.stdout)[:300]}"
        )
    return r.stdout, r.stderr


def get_diff_refs(proj, mr):
    out, err = glab_api(f"projects/{proj}/merge_requests/{mr}")
    try:
        return json.loads(out)["diff_refs"]
    except Exception:
        sys.exit(f"cannot read diff_refs for {proj}!{mr}: {(out + err)[:300]}")


def get_username():
    out, err = glab_api("user")
    try:
        return json.loads(out)["username"]
    except Exception:
        sys.exit(f"cannot read current user from `glab api user`: {(out + err)[:300]}")


def get_discussions(proj, mr):
    """All discussions of the MR. `--paginate` matters: an MR with 100+ threads
    hides the older ones on page 2+, and a partial read posts duplicates."""
    out, err = glab_api(
        f"projects/{proj}/merge_requests/{mr}/discussions?per_page=100", paginate=True
    )
    # A failed `glab` call leaves stdout empty; an MR with no threads still returns `[]`.
    # Without this the decode loop below never runs, returns [], and dedup silently turns off.
    if not out.strip():
        sys.exit(f"cannot read discussions for {proj}!{mr}: {err[:300] or 'empty response'}")
    # --paginate emits one JSON array per page, concatenated - decode them in turn.
    dec, items, i = json.JSONDecoder(), [], 0
    try:
        while i < len(out):
            page, i = dec.raw_decode(out, i)
            items += page
            while i < len(out) and out[i].isspace():
                i += 1
        return items
    except Exception:
        sys.exit(f"cannot read discussions for {proj}!{mr}: {(out + err)[:300]}")


TICKET_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
# ponytail: prefix blocklist, not a project-key lookup — these standards read exactly like keys
NOT_TICKET = {"UTF", "SHA", "AES", "RSA", "MD", "ISO", "RFC", "TLS", "HMAC", "PBKDF", "BASE", "IPV", "X"}


def find_ticket(body):
    """First ticket key in the text; a standard that looks like one (UTF-8, SHA-256) is not a ticket."""
    for m in TICKET_RE.finditer(body or ""):
        if m.group(0).split("-")[0] not in NOT_TICKET:
            return m.group(0)
    return None


def match_thread(discussions, path, line, me):
    """Is this finding's line already covered by an existing thread?

    Match is on the first note's `position.new_path` + `new_line`; a thread with
    `position: null` is a plain MR comment, not anchored to a line, and never matches.

    Returns (outcome, discussion_id, ticket):
      ("post", None, None)          - nothing there, post it
      ("mine", <id>, None)          - my own thread from a previous run
      ("theirs", <id>, <ticket>)    - someone else's thread; ticket if one is mentioned
    """
    for d in discussions:
        notes = d.get("notes") or []
        if not notes:
            continue
        pos = notes[0].get("position") or {}
        if pos.get("new_path") != path or pos.get("new_line") != line:
            continue
        if (notes[0].get("author") or {}).get("username") == me:
            return "mine", d.get("id"), None
        for n in notes:
            t = find_ticket(n.get("body"))
            if t:
                return "theirs", d.get("id"), t
        return "theirs", d.get("id"), None
    return "post", None, None


def post_thread(proj, mr, refs, path, line, body):
    payload = {
        "body": body,
        "position": {
            "position_type": "text",
            "base_sha": refs["base_sha"],
            "start_sha": refs["start_sha"],
            "head_sha": refs["head_sha"],
            "new_path": path,
            "old_path": path,
            "new_line": line,
        },
    }
    fd, fn = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps(payload).encode())
    os.close(fd)
    try:
        out, err = glab_api(
            f"projects/{proj}/merge_requests/{mr}/discussions",
            method="POST",
            headers=["Content-Type: application/json"],
            input_file=fn,
        )
    finally:
        os.unlink(fn)
    try:
        d = json.loads(out)
        n = d["notes"][0]
        pos = n.get("position") or {}
        ok = n.get("type") == "DiffNote" and pos.get("new_line") == line
        return ok, f"{d['id'][:10]} type={n.get('type')} line={pos.get('new_line')}"
    except Exception:
        return False, (out + err)[:300]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--mr", required=True)
    ap.add_argument("--threads", required=True)
    ap.add_argument("--expected-head", required=True)
    a = ap.parse_args()

    proj = a.repo if a.repo.isdigit() else quote(a.repo, safe="")
    threads = json.load(open(a.threads))
    refs = get_diff_refs(proj, a.mr)

    if refs["head_sha"] != a.expected_head:
        sys.exit(
            f"branch moved: analyzed {a.expected_head}, now {refs['head_sha']}"
        )

    me = get_username()
    discussions = get_discussions(proj, a.mr)

    ok = tried = skipped = 0
    for t in threads:
        path, line = t["path"], int(t["line"])
        short = f"{path.split('/')[-1]}:{line}"
        outcome, did, ticket = match_thread(discussions, path, line, me)
        if outcome == "mine":
            skipped += 1
            print(f"[DUP] {short} -> own thread {did}, not posted")
            continue
        if outcome == "theirs":
            skipped += 1
            tk = f" ticket={ticket}" if ticket else ""
            print(f"[SEEN] {short} -> thread {did}{tk}, not posted")
            continue
        tried += 1
        good, msg = post_thread(proj, a.mr, refs, path, line, t["body"])
        print(f"[{'OK ' if good else 'ERR'}] {short} -> {msg}")
        ok += 1 if good else 0
    print(f"--- {ok}/{tried} inline threads posted, {skipped} skipped as already covered ---")
    sys.exit(0 if ok == tried else 1)


if __name__ == "__main__":
    main()
