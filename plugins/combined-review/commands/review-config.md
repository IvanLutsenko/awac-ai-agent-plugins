---
description: "Set up combined-review: language, subagent model, CodeRabbit, security agent. Writes a config that survives plugin updates."
argument-hint: "[--project] [--show]"
allowed-tools: Bash(head:*), Bash(coderabbit:*), Bash(cat:*), Bash(ls:*), Bash(mkdir:*), Bash(which:*), Read, Write, AskUserQuestion
---

# Combined Review — config

## Where the config lives

Two files, neither inside the plugin — a plugin update or reinstall never touches them:

- **User-level (default):** `~/.claude/combined-review.md` — applies in every repo.
- **Project-level:** `.claude/combined-review.local.md` in the repo root — overrides the user file
  key by key. Add it to `.gitignore` unless the team wants a shared setting.

Resolution order for each key: project file → user file → built-in default. Missing file is not an
error; missing key falls through to the next level.

## Arguments

**$ARGUMENTS**

- no arguments → interactive setup, writes the user-level file
- `--project` → interactive setup, writes the project-level file
- `--show` → print the resolved config with the source of each value, change nothing

## Step 1 — Read what is already there

```bash
cat ~/.claude/combined-review.md 2>/dev/null
cat .claude/combined-review.local.md 2>/dev/null
which coderabbit >/dev/null 2>&1 && coderabbit auth status 2>&1 | head -5
```

With `--show`: print each key, its effective value, and where it came from (project / user / default).
Stop here.

## Step 2 — Ask (one question per key, current value as the default)

1. **Report language** — `system` (detect from CLAUDE.md or locale), `en`, `ru`, `uk`.
2. **Subagent model** — `sonnet` (default), `opus` (deeper, burns the plan faster), `haiku` (cheap,
   shallow), `inherit` (whatever the session runs on). This is what the review agents run on; the
   plugin keeps its own per-agent tuning underneath.
3. **CodeRabbit** — `auto` (use it when the CLI is installed and authenticated), `off`.
   If the CLI is missing: `npm i -g coderabbitai` or see coderabbit.ai/cli. If it is installed but
   `coderabbit auth status` says unauthenticated: `coderabbit auth login`. The plugin stores no
   CodeRabbit credentials — the CLI keeps its own.
4. **Security agent** — `auto` (default, runs on every review), `off` (runs only on `+security`). It
   is a fifth agent: the default costs one more parallel agent per review and per shard of a large
   diff.

Accept the defaults without ceremony if the user says so — the answer to all four can be «defaults».

## Step 3 — Write

Create the directory if needed, then write the file with only the keys the user chose:

```markdown
---
language: system
model: sonnet
coderabbit: auto
security: auto
---

# Combined Review config

Written by /review-config. Keys: language (system|en|ru|uk), model (sonnet|opus|haiku|inherit),
coderabbit (auto|off), security (auto|off). Project-level overrides live in
`.claude/combined-review.local.md`.
```

Report the path written and the effective values. Tell the user `/review-config --show` prints the
resolution, and that `/review` reads the file on every run — no restart needed.
