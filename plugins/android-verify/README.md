# android-verify

Verify Android changes on an emulator or a device over plain `adb`, and run Gradle so that the agent
reads a summary of the build instead of its raw output.

Version: 0.1.0

## What's New in 0.1.0

- First release: `/emu-verify` and `/gradle-run`, two helper scripts with tests, one config shared by both.

## Requirements

- Android SDK platform-tools (`adb`) on `PATH`, an emulator or a device with USB debugging;
- `python3` for the helper scripts;
- for `/gradle-run`, a Gradle wrapper in the project.

## Commands

### `/emu-verify <scenario>`

```bash
/emu-verify "open Settings, turn Dark theme on, the toolbar of the main screen turns dark"
/emu-verify "submitting the form offline shows the retry banner, not a crash" --no-install
```

1. Picks the device (`adb devices`, or `device` from the config).
2. Checks that the installed build is the one under test (`dumpsys package`: `versionName`,
   `lastUpdateTime`) and offers `/gradle-run <install_task>` when it is not.
3. Asks a person to sign in. The agent never types logins, passwords, codes or PINs.
4. Drives the scenario: `uiautomator dump` → `scripts/ui-nodes.py` lists readable and tappable nodes
   with the centre to tap → `adb shell input` → a fresh dump before every next decision.
5. Takes screenshots (written on the device, then pulled; a black capture is reported as the app's
   secure flag), and reads the app's HTTP log in logcat when the UI and the backend disagree.
6. Reports each step as expected / observed / ✅❌ with the screenshot path, plus what could not be
   verified and why.

### `/gradle-run <tasks…>`

```bash
/gradle-run :app:assembleDebug
/gradle-run :core:testDebugUnitTest --log /tmp/core-tests.log
```

Runs Gradle with all output redirected to a log in the same shell call, then prints
`scripts/gradle-summary.py`'s summary: the `BUILD …` line, failed tasks, compiler errors, failed tests
and the "What went wrong" blocks. Knows the two failures that are not the code: a file held by a stale
daemon (`--stop`, run again) and a merge of the target branch that is clean but does not compile.

## Configuration

`~/.claude/android-verify.md` (user) and `.claude/android-verify.local.md` (project, wins key by key).
Keys and defaults: [`config-defaults.md`](config-defaults.md) — `app_id`, `device`, `install_task`,
`verify_tasks`, `screenshots`, `http_log_tag`, `out_dir`. There is no key for credentials.

## Scripts

- `scripts/ui-nodes.py <dump.xml> [--find <text>] [--json]` — nodes of a uiautomator dump with their
  tap centre; exit 1 when nothing matches, 2 when the dump cannot be read.
- `scripts/gradle-summary.py <log> [--max <n>]` — the summary above; exit 0 / 1 / 2 for successful /
  failed / no result line. Reads Windows (CRLF) logs as well.

Both are covered by `tests/test_android_verify_scripts.py`.

## Codex

The commands become Codex skills through `plugin-cross-port`; the scripts are bundled into each skill.
Nothing here relies on subagents.
