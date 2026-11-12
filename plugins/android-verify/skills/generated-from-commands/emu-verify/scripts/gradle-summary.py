#!/usr/bin/env python3
"""Summarise a Gradle log so the agent reads the outcome, not thousands of lines.

Usage:
    gradle-summary.py <log> [--max <n>]

Prints the result line, the failed tasks, the "What went wrong" blocks, Kotlin
and Java compiler errors, and failed tests, each list capped at --max (20).

Exit code: 0 on BUILD SUCCESSFUL, 1 on BUILD FAILED, 2 when the log has no
result line (the build is still running, was killed, or never started) or
cannot be read. Trust this, not the exit code of a wrapper shell.
"""
import argparse
import re
import sys

RESULT = re.compile(r"^BUILD (SUCCESSFUL|FAILED)\b.*$", re.M)
FAILED_TASK = re.compile(r"^> Task (\S+) FAILED$", re.M)
KOTLIN_ERROR = re.compile(r"^e: .+$", re.M)
JAVA_ERROR = re.compile(r"^\S+\.java:\d+: error: .+$", re.M)
FAILED_TEST = re.compile(r"^(\S.*) > (.+) FAILED$", re.M)


def what_went_wrong(text):
    blocks = []
    for m in re.finditer(r"^\* What went wrong:\n(.*?)(?=^\* Try:|^\* Exception is:|^BUILD |\Z)", text, re.M | re.S):
        block = m.group(1).strip()
        if block:
            blocks.append(block)
    return blocks


def summarize(text, cap=20):
    results = list(RESULT.finditer(text))
    last = results[-1] if results else None
    tests = [f"{cls} > {name}" for cls, name in FAILED_TEST.findall(text) if not cls.startswith("> Task")]
    return {
        "result": last.group(1) if last else None,
        "result_line": last.group(0) if last else None,
        "failed_tasks": FAILED_TASK.findall(text)[:cap],
        "what_went_wrong": what_went_wrong(text)[:cap],
        "compiler_errors": (KOTLIN_ERROR.findall(text) + JAVA_ERROR.findall(text))[:cap],
        "failed_tests": tests[:cap],
    }


def render(s):
    out = [s["result_line"] or "no BUILD result line: still running, killed, or never started"]
    for title, key in (
        ("Failed tasks", "failed_tasks"),
        ("Compiler errors", "compiler_errors"),
        ("Failed tests", "failed_tests"),
    ):
        if s[key]:
            out.append(f"\n{title}:")
            out += [f"  {item}" for item in s[key]]
    if s["what_went_wrong"]:
        out.append("\nWhat went wrong:")
        for block in s["what_went_wrong"]:
            out += [f"  {ln}" for ln in block.splitlines()]
    return "\n".join(out)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--max", type=int, default=20)
    a = ap.parse_args(argv)
    try:
        with open(a.log, encoding="utf-8", errors="replace") as f:
            text = f.read().replace("\r\n", "\n")
    except OSError as error:
        print(f"cannot read {a.log}: {error}", file=sys.stderr)
        return 2
    s = summarize(text, a.max)
    print(render(s))
    return {"SUCCESSFUL": 0, "FAILED": 1}.get(s["result"], 2)


if __name__ == "__main__":
    sys.exit(main())
