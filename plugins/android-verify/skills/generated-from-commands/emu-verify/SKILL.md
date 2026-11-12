---
name: android-verify-emu-verify
description: Verify a change on an Android emulator or device over adb: check the installed build, have a person sign in, drive the scenario from uiautomator dumps, and report step by step with screenshots and backend responses. Use when the user invokes /emu-verify.
version: 0.1.0
---

> Converted from Claude Code command `/emu-verify`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.
> Helper scripts ship in this skill's own `scripts/` directory. Replace
> `<this skill directory>` with the path Codex reported when it loaded this skill —
> a bare relative path would resolve against the repository under review instead.

# Verify on a device

Runs a scenario on an emulator or a device and reports whether the change behaves as intended. Plain
`adb`: read the screen with `uiautomator dump`, act with `adb shell input`, capture with `screencap`.
No device-farm service, no MCP server in between.

**A person signs in, never the agent.** Logins, passwords, one-time codes, PINs and biometric prompts
are typed by a person at the device; the agent asks, waits for "done", and goes on.

## Context

- Directory: !`pwd`

## Arguments

**$ARGUMENTS**

- the scenario, in words: what to open, what to do, what to see;
- `--no-install` — verify what is installed now, do not offer a reinstall.

## Step 0 — Config

Two files, neither inside the plugin; each key resolves project file → user file → default:

```bash
cat .claude/android-verify.local.md 2>/dev/null    # project-level, wins
cat ~/.claude/android-verify.md 2>/dev/null        # user-level
```

Keys are described in `plugins/android-verify/config-defaults.md`. Without `app_id`, ask for the
application id once (or read it from `applicationId` in the app module's build file) and suggest
saving it in the project file.

## Step 1 — Device

```bash
adb devices
```

Exactly one device in state `device`, or the serial from `device` → use it with `adb -s <serial>` on
every call. None, several without `device` set, or `unauthorized`/`offline` → stop and say which.

Screen geometry, for comparing with a design:
```bash
adb -s <serial> shell wm size
adb -s <serial> shell wm density      # dp = px * 160 / density
```

## Step 2 — Is the build the one under test?

```bash
adb -s <serial> shell dumpsys package <app_id> | grep -E "versionName|versionCode|lastUpdateTime"
```

`versionName` often carries the branch or build number; `lastUpdateTime` older than the change means
the device runs a previous build. A stale build is the most common false "verified" — say so instead
of testing it. Unless `--no-install`, offer to install with `/gradle-run <install_task>`.

**Reinstalling usually signs the app out.** Order the run as: install, one sign-in by a person, then
the scenario — not a reinstall in the middle of it.

## Step 3 — Sign-in

If the app shows a sign-in, a code or a PIN screen, ask the person to complete it on the device and
reply when done. Do not type credentials, codes or PINs yourself, even if they are in the
conversation or in a file.

Switches that need an app restart (debug menus, feature flags) go before the sign-in: changing them
mid-scenario often signs the app out again.

## Step 4 — Drive the scenario

Repeat for every step: read the screen, decide, act, read again. Never act on a dump taken before the
last action.

```bash
mkdir -p "<out>"
adb -s <serial> shell uiautomator dump /sdcard/ui.xml && adb -s <serial> pull /sdcard/ui.xml "<out>/ui-<n>.xml"
python3 "<this skill directory>/scripts/ui-nodes.py" "<out>/ui-<n>.xml" --find "<label>"
```

`ui-nodes.py` prints each readable or tappable node as `x,y  tap  text="…" desc="…" id="…"`; `x,y` is
the centre to tap. Exit code 1 means nothing matched — the screen is not the one you expected; read
the full list before guessing.

- tap: `adb -s <serial> shell input tap <x> <y>`
- type: `adb -s <serial> shell input text '<text>'` (a space is `%s`)
- hide the keyboard: `adb -s <serial> shell input keyevent 111` (Escape). Not Back: Back can leave the
  screen instead of closing the keyboard.
- scroll: `adb -s <serial> shell input swipe <x> <y1> <x> <y2> 300`

`<out>` is `out_dir` from the config, by default `${TMPDIR:-/tmp}/android-verify/<YYYYMMDD-HHMM>`.

## Step 5 — Screenshots

```bash
adb -s <serial> shell screencap -p /sdcard/shot.png && adb -s <serial> pull /sdcard/shot.png "<out>/<n>-<what>.png"
```

Write on the device, then pull. Do not pipe a binary through `adb exec-out … > file`: some shell
wrappers (Windows ones especially) mangle it.

A screenshot that is uniformly black is the app's secure-window flag, not a rendering bug. Follow
`screenshots` from the config if it says how to lift the flag in a debug build; otherwise say that
screens cannot be captured and continue from the dumps.

## Step 6 — What the backend returned

When the UI shows something unexpected, read what the app actually received:

```bash
adb -s <serial> logcat -d -t 2000 | grep "<http_log_tag>"
```

`http_log_tag` defaults to `OkHttp`. Quote only the lines that matter, and drop authorization headers,
cookies and tokens from anything you quote.

## Step 7 — Report

- the build verified (`versionName`, `lastUpdateTime`) and the device;
- each scenario step: expected, observed, ✅/❌, with the screenshot path;
- backend excerpts that explain a ❌;
- what could not be verified and why: test data the account lacks, a step only a person can do, a
  screen the secure flag hid.

Screenshots and dumps of a test account can still carry personal data: they stay in `<out>` on this
machine unless the user decides otherwise.
