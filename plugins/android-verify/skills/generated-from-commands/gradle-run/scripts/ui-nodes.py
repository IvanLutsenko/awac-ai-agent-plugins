#!/usr/bin/env python3
"""List the nodes of a `uiautomator dump` that a scenario can read or tap.

Usage:
    ui-nodes.py <dump.xml> [--find <text>] [--json]

One line per node that carries text, a content description or a resource id,
or is clickable: its centre (the point to pass to `adb shell input tap`), the
clickable flag, and what it says. `--find` keeps the nodes whose text,
description or id contains the given text (case-insensitive). `--json` prints
the same nodes as a JSON list.

Exit code: 0 when at least one node is listed, 1 when none is (a `--find`
that matched nothing, or an empty screen), 2 when the dump cannot be read.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET

BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(value):
    m = BOUNDS.fullmatch(value or "")
    if not m:
        return None
    x1, y1, x2, y2 = (int(g) for g in m.groups())
    return x1, y1, x2, y2


def nodes(xml_text):
    root = ET.fromstring(xml_text)
    out = []
    for el in root.iter("node"):
        bounds = parse_bounds(el.get("bounds"))
        if bounds is None:
            continue
        x1, y1, x2, y2 = bounds
        if x2 <= x1 or y2 <= y1:
            continue
        text = el.get("text") or ""
        desc = el.get("content-desc") or ""
        rid = el.get("resource-id") or ""
        clickable = el.get("clickable") == "true"
        if not (text or desc or rid or clickable):
            continue
        out.append(
            {
                "x": (x1 + x2) // 2,
                "y": (y1 + y2) // 2,
                "clickable": clickable,
                "text": text,
                "desc": desc,
                "id": rid,
                "bounds": [x1, y1, x2, y2],
            }
        )
    return out


def matches(node, needle):
    needle = needle.casefold()
    return any(needle in node[k].casefold() for k in ("text", "desc", "id"))


def line(node):
    parts = [f"{node['x']},{node['y']}", "tap" if node["clickable"] else "   "]
    for key in ("text", "desc", "id"):
        if node[key]:
            parts.append(f'{key}="{node[key]}"')
    return "  ".join(parts)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--find")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        with open(a.dump, encoding="utf-8") as f:
            found = nodes(f.read())
    except (OSError, ET.ParseError) as error:
        print(f"cannot read {a.dump}: {error}", file=sys.stderr)
        return 2
    if a.find:
        found = [n for n in found if matches(n, a.find)]
    if a.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
    else:
        for n in found:
            print(line(n))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
