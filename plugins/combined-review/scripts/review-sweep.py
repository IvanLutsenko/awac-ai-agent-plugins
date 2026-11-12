#!/usr/bin/env python3
"""Review sweep: decide what every open PR/MR needs from you, then run it.

  review-sweep.py plan [--forge github|gitlab] [--out FILE]      (run from the project's clone)
  review-sweep.py run PLAN [--jobs 3] [--timeout 2400] [--only 12,15] [--panes]

`plan` classifies by the forge's own record of what you reviewed - reviewer state, approvals, the
commit your threads were opened against - never by when you last typed something: a reply posted
after a push must not mark that push as reviewed.

`run` starts each review as its own headless session (`claude -p`), so it is a main session that can
fan out its own agents - a subagent cannot. No terminal multiplexer involved. A run that exits
non-zero or prints nothing is reported as failed; it is never "no findings".
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

LARGE = 300  # changed files; above it the sweep asks before spending a review on it


def classify(pr):
    """-> (bucket, detail, steps). steps: 'rereview' | 'review' | 'review --since <sha>', in run order.

    pr: draft, files, head, ball ('mine' | 'author' | 'done'), reviewed_sha (the head your last review
    or thread was made against, None if you never looked), open_threads (your unresolved ones),
    answered (how many of those end with someone else's note), commits ([{sha, parents}], oldest first).
    """
    if pr["draft"]:
        return "hold", "draft", []
    if pr["files"] > LARGE:
        return "hold", f"{pr['files']} files changed - ask before reviewing", []
    seen, threads = pr["reviewed_sha"], pr["open_threads"]
    recheck = ["rereview"] if threads else []
    if not seen:
        if pr["ball"] == "done":
            return "done", "", []
        if threads:
            return "review", "your threads carry no commit to diff from - full review", recheck + ["review"]
        return "review", "", ["review"]
    shas = [c["sha"] for c in pr["commits"]]
    if seen == pr["head"]:
        new = []
    elif seen not in shas:
        return "review", f"the head you reviewed ({seen[:8]}) is gone - rebase or force-push", recheck + ["review"]
    else:
        new = pr["commits"][shas.index(seen) + 1:]
    # ponytail: a merge commit counts as "the target's code". One that resolved conflicts by hand can
    # carry the author's lines; merge_only is listed in the report for that reason. Diff the merge
    # against its first parent if this ever hides real code.
    own = [c for c in new if c["parents"] < 2]
    if own:  # whoever's turn the forge says it is: pushed code that nobody read is yours to read
        return "delta", f"{len(own)} new commits since {seen[:8]}", recheck + [f"review --since {seen}"]
    merges = f"only merges since {seen[:8]}: {len(new)}" if new else ""
    if pr["ball"] == "author":
        if pr["answered"]:
            return "rereview", f"waiting on the author, but {pr['answered']} of your threads got a reply", recheck
        return "waiting", merges or (f"{threads} open threads of yours" if threads else ""), []
    if pr["ball"] == "done" and not pr["answered"]:
        return "done", merges, []
    if threads:
        return "rereview", merges or (f"{pr['answered']} replies to read" if pr["answered"] else ""), recheck
    if new:
        return "merge_only", merges, []
    return "review", "review requested again, nothing of yours is open", ["review"]


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"{' '.join(cmd[:4])} ... failed ({r.returncode}): {r.stderr.strip()[:400]}")
    return r.stdout


def detect(forge):
    url = sh(["git", "remote", "get-url", "origin"]).strip()
    if "://" in url:
        host, _, path = url.split("://", 1)[1].partition("/")
    else:
        host, _, path = url.partition(":")
    host = host.split("@")[-1]
    if not forge:
        signs = {"github": "github" in host or Path(".github").is_dir(),
                 "gitlab": "gitlab" in host or Path(".gitlab-ci.yml").is_file()}
        if signs["github"] == signs["gitlab"]:
            sys.exit(f"cannot tell the forge of {host} - pass --forge github|gitlab")
        forge = "github" if signs["github"] else "gitlab"
    if forge == "github" and host != "github.com" and "." in host:  # Enterprise; not an ssh alias
        os.environ["GH_HOST"] = host
    return forge, host, path.removesuffix(".git")


def ts(stamp):
    """Forge timestamps come with and without milliseconds; as strings 'Z' sorts after '.'."""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def newest(candidates):
    """[(timestamp, sha)] -> sha of the latest, or None."""
    return max(candidates, key=lambda c: ts(c[0]))[1] if candidates else None


# --- GitHub ---------------------------------------------------------------------------------------

THREADS = """query($owner:String!,$name:String!,$n:Int!,$after:String){repository(owner:$owner,name:$name){
pullRequest(number:$n){reviewThreads(first:100,after:$after){pageInfo{hasNextPage endCursor}
nodes{isResolved first:comments(first:1){nodes{author{login} createdAt originalCommit{oid}}}
last:comments(last:1){nodes{author{login}}}}}}}}"""


def gh_json(*args):
    return json.loads(sh(["gh", *args]))


def gh_pages(path):
    return [x for page in gh_json("api", "--paginate", "--slurp", path) for x in page]


def github_threads(repo, n):
    owner, name = repo.split("/")
    nodes, after = [], None
    while True:
        args = ["api", "graphql", "-f", f"query={THREADS}", "-f", f"owner={owner}", "-f", f"name={name}",
                "-F", f"n={n}"] + (["-f", f"after={after}"] if after else [])
        page = gh_json(*args)["data"]["repository"]["pullRequest"]["reviewThreads"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        after = page["pageInfo"]["endCursor"]


def github_pr(me, pr, requested, reviews, threads, commits):
    login = lambda c: (c.get("author") or {}).get("login")
    mine = [t for t in threads if t["first"]["nodes"] and login(t["first"]["nodes"][0]) == me]
    decisive = [r for r in reviews if (r.get("user") or {}).get("login") == me
                and r["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")]
    # A review submitted with a summary is a review of that head. One without a body is what the
    # forge wraps around a single reply, and a reply must not move the reviewed head.
    summaries = [r for r in reviews if (r.get("user") or {}).get("login") == me
                 and r["state"] == "COMMENTED" and (r.get("body") or "").strip()]
    seen = newest([(r["submitted_at"], r["commit_id"]) for r in decisive + summaries]
                  + [(t["first"]["nodes"][0]["createdAt"], t["first"]["nodes"][0]["originalCommit"]["oid"])
                     for t in mine if t["first"]["nodes"][0].get("originalCommit")])
    opened = [t for t in mine if not t["isResolved"]]
    state = decisive[-1]["state"] if decisive else None
    head = pr["headRefOid"]
    # GitHub has no "waiting for author" state: the ball is theirs only while nothing moved.
    ball = ("mine" if requested or not seen or seen != head or state == "DISMISSED"
            else "done" if state == "APPROVED" else "author")
    return {"draft": pr["isDraft"], "files": pr["changedFiles"], "head": head, "ball": ball, "reviewed_sha": seen,
            "open_threads": len(opened), "answered": sum(login(t["last"]["nodes"][0]) != me for t in opened),
            "commits": [{"sha": c["sha"], "parents": len(c["parents"])} for c in commits]}


def github_plan(repo):
    me = gh_json("api", "user")["login"]
    fields = "number,title,author,isDraft,headRefOid,changedFiles,url,updatedAt"
    found, requested = {}, set()
    for query in ("review-requested:@me", "reviewed-by:@me"):
        for pr in gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "1000",
                          "--search", query, "--json", fields):
            found[pr["number"]] = pr
            if query.startswith("review-requested"):
                requested.add(pr["number"])
    for n, pr in sorted(found.items()):
        if pr["author"]["login"] == me:
            continue
        base = f"repos/{repo}/pulls/{n}"
        yield pr, github_pr(me, pr, n in requested, gh_pages(f"{base}/reviews?per_page=100"),
                            github_threads(repo, n), gh_pages(f"{base}/commits?per_page=100"))


# --- GitLab ---------------------------------------------------------------------------------------

def glab_pages(path):
    items, page = [], 1
    while batch := json.loads(sh(["glab", "api", f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}"])):
        items += batch
        page += 1
    return items


def gitlab_mr(me, mr, approved_by, state, discussions, versions, commits):
    who = lambda n: n["author"]["username"]
    mine = [d for d in discussions if d["notes"][0].get("resolvable") and who(d["notes"][0]) == me]
    opened = [d for d in mine if not d["notes"][0].get("resolved")]
    human = lambda d: [n for n in d["notes"] if not n["system"]]
    seen = [(d["notes"][0]["created_at"], d["notes"][0]["position"]["head_sha"])
            for d in mine if (d["notes"][0].get("position") or {}).get("head_sha")]
    for d in discussions:  # the head an approval was given on: the newest version that existed then
        n = d["notes"][0]
        if n["system"] and who(n) == me and n["body"] == "approved this merge request":
            seen += [(n["created_at"], v["head_commit_sha"])
                     for v in versions if ts(v["created_at"]) <= ts(n["created_at"])][:1]  # versions: newest first
    ball = ("done" if me in approved_by or state == "approved"
            else "author" if state in ("requested_changes", "reviewed") else "mine")
    return {"draft": mr["draft"], "files": int(str(mr.get("changes_count") or 0).rstrip("+") or 0),
            "head": mr["sha"], "ball": ball, "reviewed_sha": newest(seen), "open_threads": len(opened),
            "answered": sum(who(human(d)[-1]) != me for d in opened),
            "commits": [{"sha": c["id"], "parents": len(c["parent_ids"])} for c in reversed(commits)]}


def gitlab_plan(repo):
    project = f"projects/{quote(repo, safe='')}"
    me = json.loads(sh(["glab", "api", "user"]))["username"]
    for listed in glab_pages(f"{project}/merge_requests?state=opened&reviewer_username={me}"):
        if listed["author"]["username"] == me:
            continue
        base = f"{project}/merge_requests/{listed['iid']}"
        mr = json.loads(sh(["glab", "api", base]))  # the list has no changes_count
        approved_by = [a["user"]["username"] for a in json.loads(sh(["glab", "api", f"{base}/approvals"]))["approved_by"]]
        state = next((r["state"] for r in json.loads(sh(["glab", "api", f"{base}/reviewers"]))
                      if r["user"]["username"] == me), "unreviewed")
        yield ({"number": mr["iid"], "title": mr["title"], "author": {"login": mr["author"]["username"]},
                "url": mr["web_url"], "updatedAt": mr["updated_at"]},
               gitlab_mr(me, mr, approved_by, state, glab_pages(f"{base}/discussions"),
                         glab_pages(f"{base}/versions"), glab_pages(f"{base}/commits")))


# --- plan / run -----------------------------------------------------------------------------------

def plan(args):
    forge, host, repo = detect(args.forge)
    if not me_ok(forge):
        sys.exit(f"{forge} CLI is not authenticated - nothing was swept")
    items = []
    for meta, pr in (github_plan if forge == "github" else gitlab_plan)(repo):
        bucket, detail, steps = classify(pr)
        ref = f"{'!' if forge == 'gitlab' else ''}{meta['number']}"
        items.append({"number": meta["number"], "ref": ref, "title": meta["title"], "author": meta["author"]["login"],
                      "url": meta["url"], "updated": meta["updatedAt"][:10], "head": pr["head"],
                      "bucket": bucket, "detail": detail,
                      "steps": [" ".join([f"/combined-review:{s.split()[0]}", ref, *s.split()[1:]]) for s in steps]})
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="review-sweep-")) / "plan.json"
    out.write_text(json.dumps({"forge": forge, "host": host, "repo": repo, "items": items}, ensure_ascii=False, indent=1))
    print(f"{forge} {host}/{repo}: {len(items)} open PR/MR where you are a reviewer")
    for bucket in ("review", "delta", "rereview", "merge_only", "waiting", "hold", "done"):
        rows = [i for i in items if i["bucket"] == bucket]
        if rows:
            print(f"\n{bucket} ({len(rows)}):")
            for i in rows:
                print(f"  {i['ref']}  {i['title']} ({i['author']}, {i['updated']})"
                      + (f" - {i['detail']}" if i["detail"] else "")
                      + ("".join(f"\n      {s}" for s in i["steps"])))
    print(f"\nPlan: {out}")


def me_ok(forge):
    cmd = ["gh", "api", "user"] if forge == "github" else ["glab", "api", "user"]
    return shutil.which(cmd[0]) and subprocess.run(cmd, capture_output=True).returncode == 0


def run_item(item, outdir, timeout, claude):
    results = []
    for k, step in enumerate(item["steps"]):
        report = outdir / f"{item['number']}-{k}-{step.split()[0].rsplit(':', 1)[1]}.md"
        try:
            with open(report, "w") as out, open(report.with_suffix(".err"), "w") as err:
                rc = subprocess.run([claude, "-p", step], stdout=out, stderr=err, timeout=timeout).returncode
            # Exit 0 with text is not yet a review: a session that stopped early ("cannot check out ...")
            # or never loaded the command also prints something. Both reports open with a "## " heading.
            if rc:
                status = f"failed (exit {rc}, see {report.with_suffix('.err')})"
            elif not any(line.startswith("## ") for line in report.read_text().splitlines()):
                status = "failed (the session ended without a report - read the file)"
            else:
                status = "ok"
        except subprocess.TimeoutExpired:
            status = f"failed (no result in {timeout}s)"
        results.append({"step": step, "status": status, "report": str(report)})
    return {"ref": item["ref"], "head": item["head"], "results": results}


def pane_command(item):
    """What a herdr pane runs: the link, the steps still to type, then an interactive session on the first."""
    later = "".join(f"; echo {shlex.quote('then: ' + s)}" for s in item["steps"][1:])
    return f"clear; echo {shlex.quote(item['url'])}{later}; claude {shlex.quote(item['steps'][0])}"


def panes(items, per_workspace=3):
    """Opt-in, herdr only: interactive sessions to watch, three panes per workspace. Reports stay in the panes."""
    def herdr(*args):
        out = sh(["herdr", *args])
        return json.loads(out) if out.strip() else {}
    cwd = os.getcwd()
    for n in range(0, len(items), per_workspace):
        chunk = items[n:n + per_workspace]
        label = f"review {n // per_workspace + 1}"
        ids = [herdr("workspace", "create", "--cwd", cwd, "--label", label, "--no-focus")["result"]["root_pane"]["pane_id"]]
        for k in range(1, len(chunk)):  # equal columns: ratio is the share kept by the pane being split
            ids.append(herdr("pane", "split", "--pane", ids[-1], "--direction", "right", "--ratio",
                             f"{1 / (len(chunk) - k + 1):.4f}", "--cwd", cwd, "--no-focus")["result"]["pane"]["pane_id"])
        for pane, item in zip(ids, chunk):
            herdr("pane", "rename", pane, item["ref"])
            herdr("pane", "run", pane, pane_command(item))
        print(f"{label}: " + ", ".join(i["ref"] for i in chunk))


def run(args):
    plan_path = Path(args.plan)
    items = [i for i in json.loads(plan_path.read_text())["items"] if i["steps"]]
    if args.only:
        keep = {s.strip().lstrip("!") for s in args.only.split(",")}
        items = [i for i in items if str(i["number"]) in keep]
        if missing := keep - {str(i["number"]) for i in items}:
            sys.exit(f"--only: nothing to run for {', '.join(sorted(missing))} - not in the plan, or its bucket has no steps")
    if args.panes:
        if not shutil.which("herdr"):
            sys.exit("--panes needs herdr on PATH; without it, drop the flag - the headless run needs no multiplexer")
        return panes(items)
    claude = shutil.which("claude")
    if not claude:
        sys.exit("NO_HEADLESS_RUNNER: `claude` is not on PATH - run the plan's steps one after another in this session")
    outdir = Path(tempfile.mkdtemp(prefix="review-sweep-"))  # 0700: reports of private repos
    # ponytail: the sessions share one clone, so two fetches of the same base can collide on a ref
    # lock. That session then fails and is reported as failed; rerun it with --only, or use --jobs 1.
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        done = list(pool.map(lambda i: run_item(i, outdir, args.timeout, claude), items))
    (outdir / "results.json").write_text(json.dumps(done, ensure_ascii=False, indent=1))
    for d in done:
        for r in d["results"]:
            print(f"{d['ref']}  {r['status']:<8}  {r['step']}\n      {r['report']}")
    failed = sum(r["status"] != "ok" for d in done for r in d["results"])
    print(f"\n{len(done)} PR/MR, {failed} failed steps. Results: {outdir / 'results.json'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--forge", choices=["github", "gitlab"])
    a.add_argument("--out")
    b = sub.add_parser("run")
    b.add_argument("plan")
    b.add_argument("--jobs", type=int, default=3)
    b.add_argument("--timeout", type=int, default=2400)
    b.add_argument("--only")
    b.add_argument("--panes", action="store_true", help="herdr panes with interactive sessions instead of headless runs")
    args = p.parse_args()
    {"plan": plan, "run": run}[args.cmd](args)
