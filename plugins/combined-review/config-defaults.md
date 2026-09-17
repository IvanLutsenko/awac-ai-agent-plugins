---
# Combined Review — default config
# Run /review-config to write this interactively, or copy it yourself:
#   ~/.claude/combined-review.md            — user-level, applies in every repo
#   .claude/combined-review.local.md        — project-level, overrides the user file key by key
language: system
model: sonnet
coderabbit: auto
security: off
---

# Combined Review config

Neither config file lives inside the plugin, so updating or reinstalling the plugin never touches
your settings. `/review` resolves every key separately: project file → user file → the defaults
above. A missing file is not an error; a missing key falls through.

`/review-config` writes the user-level file, `/review-config --project` the project-level one, and
`/review-config --show` prints the resolved values with the source of each.

## Keys

**`language`** — language of the final report. `system` (default) detects it from the repo's
CLAUDE.md or your locale; `en`, `ru`, `uk` set it outright. Agents always work internally in English;
only the report is translated.

**`model`** — model the review subagents run on. `sonnet` (default) is the balance point; `opus` goes
deeper and burns a personal plan faster; `haiku` is cheap and shallow; `inherit` leaves each agent on
the model it declares. Per-agent tuning stays inside the plugin — this key moves all of them at once.

**`coderabbit`** — `auto` (default) runs CodeRabbit when its CLI is installed and authenticated, and
silently skips it otherwise; `off` disables the check entirely, so no install prompt and no CodeRabbit
section in the report. The plugin stores no CodeRabbit credentials: `coderabbit auth login` keeps its
own, and `coderabbit auth status` shows them.

**`security`** — `off` (default) runs the security agent only when you pass `+security`; `auto` runs
it on every review. It is a fifth parallel agent, so `auto` costs time on every review and on every
shard of a large diff.
