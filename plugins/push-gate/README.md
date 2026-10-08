# push-gate

Asks before every `git push` the model runs. The question is Claude Code's own AskUserQuestion dialog: the full command, the repository, the branch and its upstream, how many commits go, and a warning for a force push or a protected branch (`release`, `master`, `main`). A click on «Пушить» lets that one call run. «Отмена», a typed answer, Esc or a session with no one to ask (`claude -p`) refuse it, and the model reads why.

Version: 0.1.0

## What's New in 0.1.0

- The first release.

## Installation

```bash
/plugin install push-gate --marketplace IvanLutsenko/awac-ai-agent-plugins
```

**Requires** Claude Code with function hooks (mods), 2.1.287 or later. This is early access: the hook API can change between releases.

## What it asks about

- Any Bash command that holds the words `git` and `push`. The rule is coarse on purpose: it catches `bash -c "git push"`, `( git push )`, `/usr/bin/git push`, `env git push`, a quoted `-C` path and a push on the second line. A commit message with the word "push" in it costs one extra dialog.
- `glab … --push` and `gh pr create`, which push on their own.
- `claude`, `codex` or `pi` started with their guards off (`--safe-mode`, `--bare`, `--dangerously-…`).
- A command over 2000 characters is refused outright: the dialog shows every command whole, so nothing can hide past its end.

## Pairing with a PreToolUse guard

Alone, the mod refuses every push the person did not confirm. It is not a wall, though: a push from a script file, a git hook, an API call or another agent never passes through it. For a guard that also holds when mods are off (`--safe-mode`) or the mod is not installed, deny every push in a PreToolUse hook in `settings.json`:

```bash
if printf '%s' "$CMD" | grep -qw git && printf '%s' "$CMD" | grep -qw push; then
  deny 'Push only through the push-gate dialog.'
fi
```

The mod lifts that deny for the one call the person confirmed: `tool.check` runs after PreToolUse and may allow what a PreToolUse hook from user settings denied (not one from managed settings). The approval lives in the mod's memory, so there is no file the model could write to forge it. The cost: a confirmed push skips the auto mode classifier; the click is the decision.

The server is the real boundary: protect the branches that matter (no force push, no deletion) on GitHub or GitLab.

## Tests

```bash
claude plugin test plugins/push-gate
```
