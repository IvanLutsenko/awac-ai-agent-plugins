import type { Register } from 'claude-code'

// Errs toward asking: `git` and `push` as words anywhere in the line. Catches
// bash -c, subshells, /usr/bin/git, env/command prefixes, quoted -C paths and
// multi-line commands; a commit message with "push" in it costs one dialog.
// A paired PreToolUse guard should use the same rule, so both agree on a push.
export function isPush(command: string): boolean {
  return /\bgit\b/.test(command) && /\bpush\b/.test(command)
}

// Only this mod writes the token; any tool call that names it is a forgery.
export function touchesToken(input: unknown): boolean {
  return JSON.stringify(input ?? '').includes('push-gate/token')
}

const PUSH = 'Пушить'

// Only asks, never allows: on the click it writes a one-shot token with the
// exact command; a paired PreToolUse guard lets that command through once.
// The call is not rewritten, so auto mode and the classifier still judge it.
export const register: Register = on => {
  on('tool.call', ($, e, next) =>
    touchesToken(e) ? { deny: 'push-gate: its token is written by the mod alone.' } : next(e),
  ).catch(($, e, next) => (next.called ? next(e) : { deny: 'push-gate: token check failed.' }))

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!isPush(e.command)) return next(e)
    const shown = e.command.length > 300 ? `${e.command.slice(0, 300)}…` : e.command
    const answer = await $.ui.ask(`Пушу? ${shown}`, [PUSH, 'Отмена'])
    if (answer !== PUSH) return { deny: 'The person declined this push in the push-gate dialog.' }
    await $.fs.write(`${await $.env.get('HOME')}/.claude/push-gate/token`, e.command)
    return next(e)
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: 'push-gate could not ask the person; push refused.' },
  )
}
