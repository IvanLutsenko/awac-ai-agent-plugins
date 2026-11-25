#!/usr/bin/env python3
"""Run the second-vendor CLI with a deadline that is set later, not at launch.

    vendor-run.py <deadline-file> -- <cli> [args...]

The CLI runs in its own process group with stdin/stdout/stderr inherited. Every few seconds the
wrapper reads <deadline-file>: once it holds a Unix time in the past, the whole group gets TERM,
then KILL, and the wrapper exits 124. The review writes that file when every other agent has
finished, so the vendor gets "the others + N minutes", however long the others took. If the wrapper
itself gets TERM/INT/HUP, it takes the group down with it.

The backstop (VENDOR_RUN_HARD_CAP seconds, default an hour) is for a deadline that never comes —
the main agent died or is blocked on this very command. It is not a tuning knob.
"""
import os
import signal
import subprocess
import sys
import time

POLL = 2
GRACE = 5


def read_deadline(path, warned):
    try:
        with open(path) as f:
            text = f.read().strip()
    except FileNotFoundError:
        return 0.0
    except (OSError, UnicodeDecodeError) as e:
        text, err = "", e
    else:
        err = None
        if text:
            try:
                return float(text)
            except ValueError as e:
                err = e
    if err and not warned:
        print(f"vendor-run: unreadable deadline file {path}: {err}", file=sys.stderr)
        warned.append(True)
    return 0.0


def stop(proc):
    """TERM the group, give it GRACE seconds, then KILL whatever is left of it."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=GRACE)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # members that ignored TERM, even if the leader exited
    except ProcessLookupError:
        pass
    proc.wait()


def main(argv):
    if len(argv) < 4 or argv[2] != "--":
        print("usage: vendor-run.py <deadline-file> -- <cli> [args...]", file=sys.stderr)
        return 2
    deadline_file, cmd = argv[1], argv[3:]
    hard_cap = float(os.environ.get("VENDOR_RUN_HARD_CAP", 3600))
    proc = subprocess.Popen(cmd, start_new_session=True)

    def on_signal(signum, _frame):
        stop(proc)
        sys.exit(128 + signum)

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, on_signal)

    started, warned = time.time(), []
    while True:
        try:
            rc = proc.wait(timeout=POLL)
            return rc if rc >= 0 else 128 - rc
        except subprocess.TimeoutExpired:
            pass
        now = time.time()
        deadline = read_deadline(deadline_file, warned)
        # the backstop only stands in for a deadline nobody wrote; a written one always wins
        if (now > deadline) if deadline else (now - started > hard_cap):
            why = "deadline" if deadline else "hard cap"
            print(f"vendor-run: stopped after {int(now - started)}s ({why})", file=sys.stderr)
            stop(proc)
            return 124


if __name__ == "__main__":
    sys.exit(main(sys.argv))
