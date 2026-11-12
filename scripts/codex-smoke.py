#!/usr/bin/env python3
"""Does this marketplace work in Codex, not only in Claude Code? Run before `next` goes into `main`.

    python3 scripts/codex-smoke.py                # origin/next, installed into a throwaway Codex home
    python3 scripts/codex-smoke.py --ref pr/7     # any ref
    python3 scripts/codex-smoke.py --local        # the working tree as it is
    python3 scripts/codex-smoke.py --live         # plus real `codex exec` runs (needs login, spends tokens)

What it checks, per plugin of the Codex marketplace manifest:
  1. it installs from a local marketplace, at the version its manifest declares;
  2. the installed copy is self-contained - no ${CLAUDE_PLUGIN_ROOT}, every helper a skill calls is
     next to it, no path that only exists inside this repository;
  3. Codex actually offers its skills to the model (`codex debug prompt-input`: no model call, no login).
With --live: the cases in LIVE run through `codex exec` and their output is matched.

Your own ~/.codex is never touched: everything is installed into a temporary CODEX_HOME.
Exit code: 0 clean, 1 at least one FAIL, 2 the check itself could not run.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = ".agents/plugins/marketplace.json"

# (plugin, prompt, regex the last message must match). Read-only prompts only: they run in a sandbox
# with no write access, in an empty directory. Add a case when a plugin breaks in Codex in a way
# the static checks did not see.
LIVE = [
    ("combined-review",
     "Use the combined-review-review-config skill with the argument --show. Change nothing.",
     r"(?i)language"),
]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def frontmatter(text):
    if not text.startswith("---"):
        return {}
    head = text.split("---", 2)[1]
    return {k: v.strip().strip("\"'") for k, v in re.findall(r"^([\w-]+):\s*(.*)$", head, re.M)}


def check_installed(plugin, root):
    """Static checks of one installed plugin. -> (fails, warns, skill names declared under skills/)."""
    fails, warns, names = [], [], []
    for skill in sorted(root.glob("skills/**/SKILL.md")):
        rel = skill.relative_to(root)
        text = skill.read_text(encoding="utf-8")
        meta = frontmatter(text)
        if not meta.get("name") or not meta.get("description"):
            fails.append(f"{rel}: frontmatter lacks name or description - Codex will not load it")
            continue
        names.append(meta["name"])
        # used as a path, also as ${CLAUDE_PLUGIN_ROOT:-...}/; a skill may still talk about the variable
        if re.search(r"\$\{CLAUDE_PLUGIN_ROOT[^\s\"'`]*\}/", text):
            fails.append(f"{rel}: a ${{CLAUDE_PLUGIN_ROOT}}/ path is left in the text - Codex has no such variable")
        for helper in sorted(set(re.findall(r"<this skill directory>/(scripts/[\w./-]+)", text))):
            if not (skill.parent / helper).is_file():
                fails.append(f"{rel}: calls {helper}, which is not shipped next to the skill")
        for path in sorted(set(re.findall(r"(?<![\w/.-])plugins/[\w-]+/[\w./-]+", text))):
            warns.append(f"{rel}: refers to {path} - that path exists in this repository, not in an install")
    for name in sorted({n for n in names if names.count(n) > 1}):
        fails.append(f"skill name {name} is declared {names.count(name)} times")
    if not names:
        fails.append("ships no skills")
    return fails, warns, names


def offered(home, cwd):
    """{plugin: {skill}} as the model sees them, read from the rendered prompt. None if it cannot be read."""
    r = run(["codex", "debug", "prompt-input", "smoke"], env={**os.environ, "CODEX_HOME": str(home)}, cwd=cwd)
    if r.returncode:
        return None, r.stderr.strip()[-300:]
    return parse_offered(r.stdout), ""


def parse_offered(prompt_json):
    """The skills list sits inside a JSON string: lines are separated by an escaped newline."""
    seen = {}
    for plugin, skill in re.findall(r"\\n- ([\w-]+):([\w-]+): ", prompt_json):
        seen.setdefault(plugin, set()).add(skill)
    return seen


def live(home, cwd, plugins):
    """Real runs. The login is borrowed through a symlink, and handed back if Codex refreshed it."""
    real, link = Path.home() / ".codex/auth.json", home / "auth.json"
    link.symlink_to(real)
    out = []
    try:
        for plugin, prompt, expect in LIVE:
            if plugin not in plugins:
                continue
            last = home / "last-message.txt"
            last.unlink(missing_ok=True)
            try:
                r = run(["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-C", str(cwd),
                         "-o", str(last), prompt], env={**os.environ, "CODEX_HOME": str(home)}, timeout=600)
                answer = last.read_text(encoding="utf-8") if last.is_file() else ""
                if r.returncode:
                    out.append((plugin, "FAIL", f"live: codex exec exited {r.returncode}: {r.stderr.strip()[-200:]}"))
                elif not re.search(expect, answer):
                    out.append((plugin, "FAIL", f"live: answer does not match /{expect}/: {answer.strip()[:200]!r}"))
                else:
                    out.append((plugin, "ok", f"live: {prompt[:60]}"))
            except subprocess.TimeoutExpired:
                out.append((plugin, "FAIL", "live: no answer in 600s"))
    finally:
        if link.exists() and not link.is_symlink():  # Codex replaced it with refreshed tokens: keep them
            shutil.copy2(link, real)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ref", default="origin/next")
    p.add_argument("--local", action="store_true", help="check the working tree instead of --ref")
    p.add_argument("--live", action="store_true", help="also run the LIVE cases through codex exec")
    args = p.parse_args()
    if args.live and not (Path.home() / ".codex/auth.json").is_file():
        print("--live needs a Codex login (~/.codex/auth.json not found)", file=sys.stderr)
        return 2
    if not shutil.which("codex"):
        print("codex is not on PATH", file=sys.stderr)
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="codex-smoke-"))
    src, worktree = REPO, None
    rows = []  # (plugin, FAIL|warn|ok, text)
    try:
        if not args.local:
            if args.ref.startswith("origin/"):
                r = run(["git", "-C", str(REPO), "fetch", "origin", args.ref.split("/", 1)[1]])
                if r.returncode:  # a stale origin/next would pass for the current one
                    print(f"cannot fetch {args.ref}: {r.stderr.strip()}", file=sys.stderr)
                    return 2
            worktree = src = tmp / "src"
            r = run(["git", "-C", str(REPO), "worktree", "add", "--detach", str(src), args.ref])
            if r.returncode:
                print(f"cannot check out {args.ref}: {r.stderr.strip()}", file=sys.stderr)
                return 2
        sha = run(["git", "-C", str(src), "rev-parse", "--short", "HEAD"]).stdout.strip()
        manifest = json.loads((src / MANIFEST).read_text())
        market, paths = manifest["name"], {x["name"]: x["source"]["path"] for x in manifest["plugins"]}
        plugins = list(paths)
        home, cwd = tmp / "home", tmp / "cwd"
        home.mkdir(), cwd.mkdir()
        env = {**os.environ, "CODEX_HOME": str(home)}
        r = run(["codex", "plugin", "marketplace", "add", str(src)], env=env)
        if r.returncode:
            print(f"codex cannot add the marketplace: {(r.stderr or r.stdout).strip()}", file=sys.stderr)
            return 2
        declared = {}
        for plugin in plugins:
            r = run(["codex", "plugin", "add", f"{plugin}@{market}"], env=env)
            if r.returncode:
                rows.append((plugin, "FAIL", f"does not install: {(r.stderr or r.stdout).strip()[-200:]}"))
                continue
            codex_manifest = src / paths[plugin] / ".codex-plugin/plugin.json"
            if not codex_manifest.is_file():
                rows.append((plugin, "FAIL", f"{paths[plugin]}/.codex-plugin/plugin.json is missing"))
                continue
            want = json.loads(codex_manifest.read_text())["version"]
            cache = home / "plugins/cache" / market / plugin
            root = cache / want
            if not root.is_dir():
                got = sorted(d.name for d in cache.iterdir()) if cache.is_dir() else "nothing under its name"
                rows.append((plugin, "FAIL", f"installed as {got}, its Codex manifest says {want}"))
                continue
            fails, warns, declared[plugin] = check_installed(plugin, root)
            rows += [(plugin, "FAIL", f) for f in fails] + [(plugin, "warn", w) for w in warns]
        seen, err = offered(home, cwd)
        if seen is None:
            print(f"codex debug prompt-input failed: {err}", file=sys.stderr)
            return 2
        for plugin, names in declared.items():
            got = seen.get(plugin, set())
            if missing := sorted(set(names) - got):
                rows.append((plugin, "FAIL", f"Codex does not offer: {', '.join(missing)}"))
            if extra := sorted(got - set(names)):
                rows.append((plugin, "warn", f"Codex offers skills the plugin's skills/ does not declare "
                                             f"(migrated from commands/ - duplicates?): {', '.join(extra)}"))
        if args.live:
            rows += live(home, cwd, declared)
        print(f"Codex smoke: {market} at {sha} ({'working tree' if args.local else args.ref}), codex {run(['codex', '--version']).stdout.strip()}")
        for plugin in plugins:
            mine = [r for r in rows if r[0] == plugin]
            verdict = "FAIL" if any(r[1] == "FAIL" for r in mine) else "warn" if any(r[1] == "warn" for r in mine) else "ok"
            print(f"\n[{verdict:4}] {plugin}: {len(declared.get(plugin, []))} skills")
            for _, level, text in mine:
                print(f"    {level:4} {text}")
        for row in rows:
            if row[0] not in plugins:
                print(f"\n[{row[1]:4}] {row[0]}: {row[2]}")
        failed = sum(r[1] == "FAIL" for r in rows)
        print(f"\n{len(plugins)} plugins, {failed} FAIL, {sum(r[1] == 'warn' for r in rows)} warn"
              + ("" if args.live else " - static + discovery only; --live runs real sessions"))
        return 1 if failed else 0
    except (OSError, ValueError, KeyError) as e:  # a broken manifest, an unreadable install: not a verdict
        print(f"the check could not run: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        if worktree:
            run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(worktree)])
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
