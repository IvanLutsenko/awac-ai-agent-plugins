# push-gate

Asks before every `git push` the model runs. The question is Claude Code's own AskUserQuestion dialog: «Пушу? <command>» with «Пушить» and «Отмена». A click on «Пушить» lets that one command run. «Отмена», a typed answer, Esc or a session with no one to ask (`claude -p`) refuse it, and the model reads why.

Version: 0.1.0

## What's New in 0.1.0

- The first release.

## Installation

```bash
/plugin install push-gate --marketplace IvanLutsenko/awac-ai-agent-plugins
```

**Requires** Claude Code with function hooks (mods), 2.1.287 or later. This is early access: the hook API can change between releases.

## What counts as a push

Any Bash command that holds the words `git` and `push`. The rule is coarse on purpose: it catches `bash -c "git push"`, `( git push )`, `/usr/bin/git push`, `env git push`, a quoted `-C` path and a push on the second line. A commit message or a heredoc with the word "push" in it costs one extra dialog.

## Why it does not allow the call

The mod only asks. It never answers `tool.check` with `allow`, and it never rewrites the call. So the auto mode classifier still judges the push, and auto mode does not refuse the call as rewritten after the model wrote it.

## Pairing with a PreToolUse guard

A guard in `settings.json` runs after the mod. Alone, the mod already refuses every push the person did not confirm. A guard that denies every push is also safe when mods are off (`--safe-mode`) or in a session where the mod is not installed. The two need a way to agree, and that is a one-shot token:

- On «Пушить» the mod writes the exact command to the file `token` in `~/.claude/push-gate/`.
- The guard lets a command through when it equals the token and the token is under 60 seconds old, and deletes the token.
- Any tool call that names the token's path is refused, by the mod and by the guard, so the model cannot write a token itself by naming the file. A script that writes it without naming it is not caught: this stops mistakes, not a model that sets out to get around it.

The guard's part, before its own push check:

```bash
PG_DIR="$HOME/.claude/push-gate"
PG_TOKEN="$PG_DIR/token"
if [ -f "$PG_TOKEN" ] && [ "$(cat "$PG_TOKEN")" = "$CMD" ] && [ $(( $(date +%s) - $(stat -f %m "$PG_TOKEN") )) -lt 60 ]; then
  rm -f "$PG_TOKEN"; exit 0
fi
```

(`stat -f %m` is macOS; on Linux it is `stat -c %Y`.)

## Tests

```bash
claude plugin test plugins/push-gate
```
