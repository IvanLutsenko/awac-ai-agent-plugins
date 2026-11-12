---
# android-verify — default config
# Copy the keys you need into one of:
#   ~/.claude/android-verify.md               — user-level
#   .claude/android-verify.local.md           — project-level, wins key by key (keep it out of git)
app_id:
device:
install_task:
verify_tasks:
screenshots:
http_log_tag: OkHttp
out_dir:
---

# android-verify config

Neither file lives inside the plugin, so updating it never touches your settings. Each key resolves
separately: project file → user file → the defaults above.

## Keys

**`app_id`** — the application id under test (`com.example.app`, or a debug suffix of it). Required by
`/emu-verify`; it asks once when missing.

**`device`** — an adb serial (`emulator-5554`). Empty: the only connected device.

**`install_task`** — the Gradle task that installs the build under test (`:app:installDebug`).
`/emu-verify` offers it when the installed build is stale.

**`verify_tasks`** — compile and static-analysis tasks `/gradle-run` suggests after a merge of the
target branch (`:app:compileDebugKotlin detekt`). Empty: name them per case.

**`screenshots`** — free text: how a debug build lets screenshots through when the app sets the
secure-window flag (a debug-menu switch, a build flag). Empty: a black capture is reported as such.

**`http_log_tag`** — the logcat tag of the app's HTTP logger, used to read backend responses.

**`out_dir`** — where dumps and screenshots go. Empty: `${TMPDIR:-/tmp}/android-verify/<timestamp>`.

Credentials have no key on purpose: a person signs in at the device.
