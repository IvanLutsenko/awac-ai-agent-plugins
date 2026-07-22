#!/usr/bin/env python3
"""Post inline, resolvable review threads to a GitLab MR as diff-anchored notes.

Encodes the ONE mechanism that actually anchors a note to a line:
a JSON body with a nested `position` object sent via `glab api --input`
with an explicit `Content-Type: application/json` header.

Do NOT use `glab api -f "position[new_line]=.."`: the bracket keys are sent
as flat JSON keys, GitLab ignores them, and you silently get a plain
(non-anchored) comment instead of an inline thread.

Usage:
    post-gitlab-mr-threads.py --repo <path-or-id> --mr <iid> --threads <file.json>

  --repo     "group/project" (URL-encoded automatically) or numeric project id
  --mr       MR iid (the !N number)
  --threads  JSON file: [{"path": "...", "line": 42, "body": "..."}, ...]
             `line` is the line number in the NEW (post-change) file; it must be
             an added or in-hunk line of the MR diff, or GitLab rejects it.

Reads diff_refs from the MR itself, so the caller only supplies findings.
Exit code is non-zero if any thread failed to anchor.
"""
import argparse, json, subprocess, sys, tempfile, os
from urllib.parse import quote


def glab_api(path, method=None, headers=None, input_file=None):
    args = ["glab", "api", path]
    if method:
        args += ["-X", method]
    for h in headers or []:
        args += ["-H", h]
    if input_file:
        args += ["--input", input_file]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout, r.stderr


def get_diff_refs(proj, mr):
    out, err = glab_api(f"projects/{proj}/merge_requests/{mr}")
    try:
        return json.loads(out)["diff_refs"]
    except Exception:
        sys.exit(f"cannot read diff_refs for {proj}!{mr}: {(out + err)[:300]}")


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
    a = ap.parse_args()

    proj = a.repo if a.repo.isdigit() else quote(a.repo, safe="")
    threads = json.load(open(a.threads))
    refs = get_diff_refs(proj, a.mr)

    ok = 0
    for t in threads:
        good, msg = post_thread(proj, a.mr, refs, t["path"], int(t["line"]), t["body"])
        tag = "OK " if good else "ERR"
        print(f"[{tag}] {t['path'].split('/')[-1]}:{t['line']} -> {msg}")
        ok += 1 if good else 0
    print(f"--- {ok}/{len(threads)} inline threads posted ---")
    sys.exit(0 if ok == len(threads) else 1)


if __name__ == "__main__":
    main()
