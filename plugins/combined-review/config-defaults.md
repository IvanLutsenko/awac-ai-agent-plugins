---
# Combined Review — default config
# Run /review-config to write this interactively, or copy it yourself:
#   ~/.claude/combined-review.md            — user-level, applies in every repo
#   .claude/combined-review.local.md        — project-level, overrides the user file key by key
language: system
model: sonnet
coderabbit: auto
voice:
rules:
---

# Combined Review config

Neither config file lives inside the plugin, so updating or reinstalling the plugin never touches
your settings. `/review` resolves every key separately: project file → user file → the defaults
above. A missing file is not an error; a missing key falls through.

`/review-config` writes the user-level file, `/review-config --project` the project-level one, and
`/review-config --show` prints the resolved values with the source of each.

## Keys

**`language`** — language of the final report. `system` (default) detects it from the repo's
CLAUDE.md or your locale; `en`, `ru`, `uk` set it outright. Agents get the resolved language up
front and return their findings already in it; nothing is translated afterwards.

**`model`** — model the review subagents run on. `sonnet` (default) is the balance point; `opus` goes
deeper and burns a personal plan faster; `haiku` is cheap and shallow; `inherit` leaves each agent on
the model it declares. Per-agent tuning stays inside the plugin — this key moves all of them at once.

**`coderabbit`** — `auto` (default) runs CodeRabbit when its CLI is installed and authenticated, and
silently skips it otherwise; `off` disables the check entirely, so no install prompt and no CodeRabbit
section in the report. The plugin stores no CodeRabbit credentials: `coderabbit auth login` keeps its
own, and `coderabbit auth status` shows them.

**`voice`** — empty (default) or a path to a file describing how you write review comments. Only
`+threads` reads it: before posting, each thread is reworded by that file — claim first in your words,
then the evidence. What gets found and the terminal report stay as they are. It is personal, so keep it
in the user-level file.

**`rules`** — empty (default) or a path to a file of review rules kept outside the repository: limits
stricter than the linter, conventions a team follows that the repo's `CLAUDE.md`/`AGENTS.md` do not
(yet) carry. `~` expands; a relative path is read from the repository root. The agents get it beside the
repo policy files and cite it as reviewer rules; where the two disagree, the repo policy wins and the
report says so. It comes from your config, not from the branch under review, so an MR author cannot
change it. Usually per project, so it belongs in the project-level file.

**There is no key for the agents.** All five run on every review, security included — which agent
turns out to be the useful one changes per diff, and one that reports nothing has still ruled things
out. Five agents cost roughly five times the tokens of a single pass; the lever for that is `model`,
not a shorter roster. A `security:` key left over from an older config is ignored.
