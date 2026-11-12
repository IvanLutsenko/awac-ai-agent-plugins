---
# plan-gate — default config
# Copy the keys you need into one of:
#   ~/.claude/plan-gate.md               — user-level
#   .claude/plan-gate.local.md           — project-level, wins key by key
executor_model: sonnet
review: auto
max_change:
verify:
---

# plan-gate config

Neither file lives inside the plugin, so updating it never touches your settings. Each key resolves
separately: project file → user file → the defaults above.

## Keys

**`executor_model`** — the model the `executor` agent runs on: `sonnet` (default), `haiku` for plans
that are close to mechanical, `opus` when the steps still need judgement (then the gate buys less),
`inherit` for the session's model. Codex has no per-agent model: there the session carries out the plan.

**`review`** — how the diff is checked in Step 5. `auto` (default): `/review` from the
`combined-review` plugin when it is installed, an inline check against the plan otherwise. `inline`:
always the inline check.

**`max_change`** — a limit on changed lines per PR/MR the repository works with (`500`). When the
estimate exceeds it, the plan splits the work into consecutive changes. Empty: no slicing.

**`verify`** — the commands that prove a change works in this repository (`./gradlew testDebugUnitTest
detekt`, `npm test`). The plan uses them in its **Verify** section. Empty: the plan names them per task.
