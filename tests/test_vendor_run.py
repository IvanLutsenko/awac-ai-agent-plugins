import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/combined-review/scripts/vendor-run.py"


def start(tmp_path, cmd, env=None):
    return subprocess.Popen([sys.executable, str(SCRIPT), str(tmp_path / "deadline"), "--", *cmd],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env={**os.environ, **(env or {})})


def run(tmp_path, cmd, deadline=None, env=None):
    if deadline is not None:
        (tmp_path / "deadline").write_text(str(deadline))
    p = start(tmp_path, cmd, env)
    out, err = p.communicate("hello", timeout=60)
    return p.returncode, out, err


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def wait_gone(pid, seconds=3):
    end = time.time() + seconds
    while time.time() < end and alive(pid):
        time.sleep(0.1)
    return not alive(pid)


def stubborn_grandchild(tmp_path):
    """A shell whose background child ignores TERM and records its pid."""
    pidfile = tmp_path / "gc.pid"
    return pidfile, ["sh", "-c", f"sh -c 'trap \"\" TERM; echo $$ > {pidfile}; sleep 60' & sleep 60"]


def test_passes_exit_code_stdin_and_output(tmp_path):
    rc, out, _ = run(tmp_path, ["sh", "-c", "cat; exit 3"])
    assert rc == 3 and out == "hello"


def test_future_deadline_lets_it_finish(tmp_path):
    rc, out, _ = run(tmp_path, ["sh", "-c", "sleep 3; echo done"], deadline=time.time() + 60)
    assert rc == 0 and out.strip() == "done"


def test_deadline_written_mid_run_stops_it(tmp_path):
    p = start(tmp_path, ["sleep", "60"])
    time.sleep(3)
    assert p.poll() is None  # no deadline yet: still running
    (tmp_path / "deadline").write_text(str(time.time()))
    p.communicate(timeout=20)
    assert p.returncode == 124


def test_deadline_kills_group_including_term_ignoring_child(tmp_path):
    pidfile, cmd = stubborn_grandchild(tmp_path)
    rc, _, err = run(tmp_path, cmd, deadline=time.time() - 1)
    assert rc == 124 and "deadline" in err
    assert wait_gone(int(pidfile.read_text()))


def test_hard_cap_without_deadline(tmp_path):
    rc, _, err = run(tmp_path, ["sleep", "60"], env={"VENDOR_RUN_HARD_CAP": "3"})
    assert rc == 124 and "hard cap" in err


def test_killing_the_wrapper_takes_the_group_down(tmp_path):
    pidfile, cmd = stubborn_grandchild(tmp_path)
    p = start(tmp_path, cmd)
    end = time.time() + 10
    while not pidfile.exists() and time.time() < end:
        time.sleep(0.1)
    p.send_signal(signal.SIGTERM)
    p.communicate(timeout=20)
    assert p.returncode == 128 + signal.SIGTERM
    assert wait_gone(int(pidfile.read_text()))


def test_written_deadline_overrides_hard_cap(tmp_path):
    rc, out, _ = run(tmp_path, ["sh", "-c", "sleep 4; echo done"], deadline=time.time() + 60,
                     env={"VENDOR_RUN_HARD_CAP": "1"})
    assert rc == 0 and out.strip() == "done"


def test_unreadable_deadline_is_reported_not_silent(tmp_path):
    rc, _, err = run(tmp_path, ["sh", "-c", "sleep 3"], deadline="garbage")
    assert rc == 0 and "unreadable deadline file" in err


def test_signal_death_maps_to_128_plus(tmp_path):
    rc, _, _ = run(tmp_path, ["sh", "-c", "kill -TERM $$"])
    assert rc == 128 + 15


def test_usage_error(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPT), "x", "codex"], capture_output=True, text=True)
    assert p.returncode == 2 and "usage" in p.stderr
