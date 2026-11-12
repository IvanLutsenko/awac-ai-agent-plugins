#!/usr/bin/env python3
"""Check agent findings against the position map — mechanically, not by promise.

Usage:
  filter-findings.py --findings <file> --positions <file> --root <dir> [--json]

  --findings   agent output, one finding per line, each carrying a `path:line`
               (`- [critical] src/foo.ts:42 — ...`, `1. \\`src/foo.ts:42\\` — ...`)
  --positions  the position map built in Step 5: `path:line` per line
  --root       repository root at the revision under review (worktree or cwd)

Prints one verdict per finding and a summary:

  [KEEP ] the cited line is a line this diff touched
  [MOVED] the line was wrong; the quoted code was found on a line that IS in the
          map, so the finding is re-anchored there
  [DROP ] the file is untouched by this diff, or the quoted code isn't in it
  [?????] no `path:line` could be parsed out of the line at all

A wrong line is not the same as out of scope: agents miscount, and the usual
failure is quoting a position inside the saved .diff, which points past the end
of short files. Dropping those silently deletes real defects, so they are
re-anchored where the code says they belong, or reported as unparsed — never
discarded quietly.

Exit code: 0 when every finding was classified, 1 when the position map is empty
(a broken map, not an empty change) or something could not be parsed.
"""
import argparse, json, re, sys
from pathlib import Path

# `path:line`, optionally in backticks. The path must look like a path: it carries
# a `/` or a dot, so prose like "step 5:42" is not mistaken for one.
ANCHOR_RE = re.compile(r"`?([\w./@+-]*[/.][\w./@+-]*):(\d+)`?")
# A quoted snippet to re-anchor by: backticked, at least 4 chars, not itself a path:line.
SNIPPET_RE = re.compile(r"`([^`\n]{4,})`")


def load_positions(path):
    pairs, files = set(), set()
    for raw in Path(path).read_text().splitlines():
        raw = raw.strip()
        if not raw or ":" not in raw:
            continue
        f, _, n = raw.rpartition(":")
        pairs.add((f, n))
        files.add(f)
    return pairs, files


def parse_finding(text):
    """(path, line, snippet) for the first anchor in the line, or None."""
    m = ANCHOR_RE.search(text)
    if not m:
        return None
    path, line = m.group(1), m.group(2)
    snippet = None
    for s in SNIPPET_RE.findall(text):
        if ANCHOR_RE.fullmatch(s.strip()):
            continue
        snippet = s.strip()
        break
    return path, line, snippet


def reanchor(root, path, snippet, pairs):
    """Line number where the quoted code actually sits, if that line is in the map."""
    if not snippet:
        return None, "no quoted code to search for"
    f = Path(root) / path
    if not f.is_file():
        return None, "file not present at the reviewed revision"
    try:
        lines = f.read_text(errors="replace").splitlines()
    except OSError as e:
        return None, f"cannot read file: {e}"
    hits = [str(i) for i, l in enumerate(lines, 1) if snippet in l]
    mapped = [h for h in hits if (path, h) in pairs]
    if len(mapped) == 1:
        return mapped[0], None
    if not hits:
        return None, "quoted code not found in the file"
    if not mapped:
        return None, f"quoted code sits on line(s) {','.join(hits)}, untouched by this diff"
    return None, f"quoted code is ambiguous, on lines {','.join(mapped)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", required=True)
    ap.add_argument("--positions", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--json", action="store_true", help="machine-readable verdicts on stdout")
    a = ap.parse_args()

    pairs, files = load_positions(a.positions)
    if not pairs:
        print("POSITION MAP EMPTY - do not filter, report the findings as they came")
        return 1

    out, counts = [], {"keep": 0, "moved": 0, "drop": 0, "unparsed": 0}
    for raw in Path(a.findings).read_text().splitlines():
        if not raw.strip():
            continue
        parsed = parse_finding(raw)
        if not parsed:
            counts["unparsed"] += 1
            out.append({"verdict": "unparsed", "text": raw.strip()})
            continue
        path, line, snippet = parsed
        if (path, line) in pairs:
            counts["keep"] += 1
            out.append({"verdict": "keep", "path": path, "line": line, "text": raw.strip()})
        elif path in files:
            new, why = reanchor(a.root, path, snippet, pairs)
            if new:
                counts["moved"] += 1
                out.append({"verdict": "moved", "path": path, "line": new,
                            "was": line, "text": raw.strip()})
            else:
                counts["drop"] += 1
                out.append({"verdict": "drop", "path": path, "line": line,
                            "reason": f"line not in the diff; {why}", "text": raw.strip()})
        else:
            counts["drop"] += 1
            out.append({"verdict": "drop", "path": path, "line": line,
                        "reason": "file untouched by this diff", "text": raw.strip()})

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for r in out:
            if r["verdict"] == "keep":
                print(f"[KEEP ] {r['path']}:{r['line']}")
            elif r["verdict"] == "moved":
                print(f"[MOVED] {r['path']}:{r['was']} -> {r['line']} (found the quoted code there)")
            elif r["verdict"] == "drop":
                print(f"[DROP ] {r['path']}:{r['line']} - {r['reason']}")
            else:
                print(f"[?????] no file:line in: {r['text'][:80]}")
    print(f"--- {counts['keep']} kept, {counts['moved']} re-anchored, "
          f"{counts['drop']} dropped, {counts['unparsed']} unparsed ---")

    # Unparsed findings are not a clean run: something was said and nobody placed it.
    return 1 if counts["unparsed"] else 0


if __name__ == "__main__":
    sys.exit(main())
