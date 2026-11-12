---
description: "Run Gradle tasks with the output in a log file: the agent reads the result, the failed tasks and the first errors instead of thousands of lines."
argument-hint: "<tasks…> [--log <path>]"
allowed-tools: Bash(./gradlew:*), Bash(gradlew:*), Bash(gradlew.bat:*), Bash(cmd:*), Bash(python3:*), Bash(tail:*), Bash(mkdir:*), Bash(date:*), Bash(find:*), Bash(ls:*), Read
---

# Gradle, read through its log

A full Android build prints thousands of lines; read through a terminal tool, they flood its output
limit long before the error. Redirect everything to a log, then read the summary.

## Arguments

**$ARGUMENTS**

- the Gradle tasks, as you would pass them to `gradlew`;
- `--log <path>` — where to write the log; default `${TMPDIR:-/tmp}/gradle-<YYYYMMDD-HHMMSS>.log`
  (`%TEMP%` on Windows).

## Step 1 — Run, redirected in the same shell call

macOS / Linux:
```bash
./gradlew <tasks> --console=plain > "<log>" 2>&1; echo "exit=$?"
```

Windows (`cmd`):
```bat
gradlew.bat <tasks> --console=plain > "<log>" 2>&1 & echo exit=%ERRORLEVEL%
```

Redirect inside the call that runs Gradle. Do not detach it (`&`, `start /b`, `nohup` from a wrapper
that exits): the child dies with the wrapper and leaves an empty log. If the build outlives the tool's
time limit, use the tool's own way of running long commands and poll — still with the redirect.

## Step 2 — Read the summary

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gradle-summary.py" "<log>"
```

It prints the `BUILD …` line, failed tasks, compiler errors, failed tests and the "What went wrong"
blocks. Exit code 0 = successful, 1 = failed, 2 = no result line yet. Trust it over the exit code of a
wrapper shell, which on some setups reports success for a failed build. Open the log around a line only
when the summary is not enough.

## Step 3 — Known failures that are not the code

- **A file held by another process** ("used by another process", "Unable to delete", a locked
  `classes.jar`): a stale daemon. `./gradlew --stop`, then run once more.
- **After merging the target branch in**: a merge without conflicts is not a merge that compiles.
  Compile and run static analysis for the modules the merge touched — `verify_tasks` from the config
  when set — not only the module you changed.

## Step 4 — Which APK was built

For an assemble or install task, read the variant's `output-metadata.json`:
```bash
find . -path "*/build/outputs/apk/*" -name output-metadata.json
```
`versionName` and `versionCode` come from it, not from the log: a task that was up to date prints
nothing about the version. A file older than the run belongs to an earlier build or another variant.

## Step 5 — Report

The result line, failed tasks, the first errors with `file:line`, the APK version when one was built,
and the log path. Never paste the whole log.
