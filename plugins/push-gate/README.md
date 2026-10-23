# push-gate

Asks before every `git push` the model runs. The question is Claude Code's own AskUserQuestion dialog: the full command, the repository, the branch and its upstream, how many commits go, and a warning for a force push or a protected branch (`release`, `master`, `main`). A click on «Пушить» lets that one call run. «Отмена», a typed answer, Esc or a session with no one to ask (`claude -p`) refuse it, and the model reads why.

Version: 0.2.0

## What's New in 0.2.0

- A confirmed command now runs from the mod itself, and its output reaches the model as the Bash call's result. Lifting a PreToolUse deny in `tool.check` stopped working in Claude Code 2.1.308: a managed-tier hook there hands the event past the user tier, so the click was asked for and then the push was denied anyway.
- The command runs under `bash -c` in the session's working directory, not in the Bash tool's shell: a `cd` from an earlier Bash call does not carry over, so give the repository with `git -C <path>`. Ten minutes at most.

## What's New in 0.1.1

- A push is `push` as git's subcommand, not the word anywhere in the line: a path like `core/push/…`, a `grep` pattern or a commit message no longer opens the dialog.
- The force and protected-branch warnings read only the push's own arguments: `merge-base origin/release` next to it is not a protected push.
- The repository line expands `-C "$R"` from an `R=…` earlier in the same command and takes the `-C` of the push itself, not of the first `git`.
- An inline alias (`git -c alias.p=push p`) still asks.

## What's New in 0.1.0

- The first release.

## Installation

```bash
/plugin install push-gate --marketplace IvanLutsenko/awac-ai-agent-plugins
```

**Requires** Claude Code with function hooks (mods), 2.1.308 or later. This is early access: the hook API can change between releases.

## What it asks about

- Any Bash command where `git`, then its global options (`-C <path>`, `-c <k=v>`, `--git-dir=…`, `--no-pager`), then `push` stand in a row. It catches `bash -c "git push"`, `( git push )`, `/usr/bin/git push`, `env git push`, a quoted `-C` path, a push on the second line or after a backslash-newline, and a git alias set inline with `-c alias.…`. The word `push` in a path, a `grep` pattern or a commit message does not count.
- `glab … --push` and `gh pr create`, which push on their own.
- `claude`, `codex` or `pi` started with their guards off (`--safe-mode`, `--bare`, `--dangerously-…`).
- A command over 2000 characters is refused outright: the dialog shows every command whole, so nothing can hide past its end.

## Pairing with a PreToolUse guard

Alone, the mod refuses every push the person did not confirm. It is not a wall, though: a push from a script file, a git hook, an API call or another agent never passes through it. For a guard that also holds when mods are off (`--safe-mode`) or the mod is not installed, deny every push in a PreToolUse hook in `settings.json`:

```bash
# Same rule as GIT_PUSH in hooks/register.ts; keep the two in step.
read -r PUSH_RE <<'RE'
(^|[^[:alnum:]_.-])git(([[:space:]]+(-C|-c|--git-dir|--work-tree|--namespace)([[:space:]]+|=)("[^"]*"|'[^']*'|[^[:space:]]+)|[[:space:]]+--?[[:alnum:]_-]+(=[^[:space:]]*)?))*[[:space:]]+["']?push([[:space:];&|)"']|$)|(^|[^[:alnum:]_.-])git[[:space:]]([^;&|]*[[:space:]])?-c[[:space:]]*alias\.
RE
if printf '%s\n' "$CMD" | awk '{ if (sub(/\\$/, "")) printf "%s ", $0; else print }' | grep -qE "$PUSH_RE"; then
  deny 'Push only through the push-gate dialog.'
fi
```

A guard with a coarser rule than the mod's denies pushes the mod never asks about; a finer one lets them through unasked.

The mod does not lift that deny: on the click it runs the confirmed command itself and answers the call with its output, so PreToolUse and `tool.check` never see that one call, and the guard keeps denying every other push. The approval is the click itself, so there is nothing the model could write to forge it. The cost: a confirmed push runs outside the permission system, the auto mode classifier and any managed `tool.check` hook included; the click is the decision.

The server is the real boundary: protect the branches that matter (no force push, no deletion) on GitHub or GitLab.

## Tests

```bash
claude plugin test plugins/push-gate
```
