# plan-gate

Plan, approve, execute, verify. The plan is written and shown first, nothing in the repository changes
until a person approves it, an executor agent on a cheaper model carries it out, and the diff is
checked against the plan before anyone hears it is done.

Version: 0.1.0

## What's New in 0.1.0

- First release: `/plan-gate` and the `executor` agent.

## Why

Planning and review need the strongest model; carrying out a precise plan does not. Running both on
the strong model burns the plan's budget on typing; running both on a cheap one ships its design
mistakes. The gate in the middle is where a person catches a wrong plan while it is still cheap to fix.

```
task text ─► gather (read only) ─► plan file ─► GATE: person approves ─► executor (sonnet) ─► verify + review ─► report
                                       ▲                 │ change                                    │ findings (≤ 2 rounds)
                                       └─────────────────┘                          executor ◄────────┘
```

## Usage

```bash
/plan-gate "add a retry banner to the upload screen when the request times out"
/plan-gate docs/specs/export-csv.md
/plan-gate --resume ~/.local/state/plan-gate/my-app/2026-11-12-export-csv.md
```

The input is the task's text, so any tracker works: paste the ticket.

The plan goes to `${XDG_STATE_HOME:-~/.local/state}/plan-gate/<repo>/`, outside the repository, with
Goal, Scope, Steps (files and changes, no design left to the executor), Tests, Verify, Slicing (when
`max_change` is set), Do not, and Open questions.

At the gate only an explicit approval moves on. A non-interactive run stops after the plan.

The `executor` agent changes only the files the plan names, runs the checks it lists, and stops at the
first step it cannot do as written. No commits, pushes, dependency changes or test edits made just to
pass unless the plan says so.

Step 5 runs the plan's Verify commands and reviews the diff — with `/review` when `combined-review` is
installed, otherwise inline against the plan. Findings go back to the executor, two rounds at most.

## Configuration

`~/.claude/plan-gate.md` (user) and `.claude/plan-gate.local.md` (project, wins key by key). Keys:
[`config-defaults.md`](config-defaults.md) — `executor_model`, `review`, `max_change`, `verify`.

## Codex

Through `plugin-cross-port` the command becomes a skill and the agent a standalone skill. Codex cannot
launch a subagent or choose its model, so there the session carries out the approved plan itself; the
gate is the same.
