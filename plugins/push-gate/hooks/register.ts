import type { EngineInterface, Register } from 'claude-code'

const PUSH = 'Пушить'
const MAX_SHOWN = 2000
const PROTECTED = /\b(release|master|main)\b/

// Errs toward asking. A push is `git` and `push` as words anywhere in the line
// (bash -c, subshells, /usr/bin/git, env prefixes, quoted -C paths, newlines);
// also the tools that push on their own and child agents started with their
// guards off. A commit message with "push" in it costs one extra dialog.
export function needsConfirm(command: string): boolean {
  return (
    (/\bgit\b/.test(command) && /\bpush\b/.test(command)) ||
    /\bglab\b[^\n]*--push\b/.test(command) ||
    /\bgh\s+pr\s+create\b/.test(command) ||
    /\b(claude|codex|pi)\b[^\n]*--(safe-mode|bare|dangerously-[\w-]+)/.test(command)
  )
}

export function warnings(command: string, branch?: string): string[] {
  const marks: string[] = []
  if (/(^|\s)(--force|--force-with-lease|-[a-zA-Z]*f[a-zA-Z]*)(\s|=|$)|\s\+\S/.test(command)) marks.push('FORCE')
  if (PROTECTED.test(command) || (branch !== undefined && PROTECTED.test(branch))) marks.push('защищённая ветка')
  return marks
}

// Where the push runs: git's -C path when given, else the session's directory.
export function repoDir(command: string): string | undefined {
  const m = command.match(/\bgit\s+-C\s+(?:"([^"]+)"|'([^']+)'|(\S+))/)
  return m === null ? undefined : (m[1] ?? m[2] ?? m[3])
}

async function git($: EngineInterface, cwd: string, ...args: string[]): Promise<string | undefined> {
  try {
    const run = await $.process.run(['git', ...args], { cwd, timeoutMs: 3000 })
    return run.exitCode === 0 ? run.stdout.trim() : undefined
  } catch {
    return undefined
  }
}

async function question($: EngineInterface, command: string): Promise<string> {
  const cwd = repoDir(command) ?? (await $.session.cwd())
  const branch = await git($, cwd, 'rev-parse', '--abbrev-ref', 'HEAD')
  const upstream = await git($, cwd, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
  const ahead = upstream === undefined ? undefined : await git($, cwd, 'rev-list', '--count', '@{u}..HEAD')
  const marks = warnings(command, branch)

  return [
    'Пушу?',
    command,
    '',
    `Репо: ${cwd}`,
    `Ветка: ${branch ?? '?'} → ${upstream ?? 'нет upstream'}${ahead === undefined ? '' : ` (коммитов впереди: ${ahead})`}`,
    ...(marks.length > 0 ? [`ВНИМАНИЕ: ${marks.join(' · ')}`] : []),
  ].join('\n')
}

// The mod asks in tool.call and, on the click, lifts the deny of a PreToolUse
// guard for that one call in tool.check (which runs after PreToolUse). The
// approval lives in this module's memory, out of the model's reach: there is
// no file to forge. A confirmed push skips the auto mode classifier; the
// click is the decision.
export const register: Register = on => {
  const approved = new Set<string>()

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!needsConfirm(e.command)) return next(e)
    if (e.command.length > MAX_SHOWN) {
      return { deny: `push-gate: the command is longer than ${MAX_SHOWN} characters and cannot be shown whole; split it.` }
    }

    const answer = await $.ui.ask(await question($, e.command), { options: [PUSH, 'Отмена'], header: 'push-gate' })
    if (answer !== PUSH) return { deny: 'The person declined this push in the push-gate dialog.' }

    approved.add(e.tool_use_id)
    try {
      return await next(e)
    } finally {
      approved.delete(e.tool_use_id)
    }
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: 'push-gate could not ask the person; push refused.' },
  )

  // ponytail: no .catch — a failure here only fails to lift a deny, which is safe.
  on('tool.check', { tool: 'Bash' }, ($, e, next) =>
    e.tool_use_id !== undefined && approved.has(e.tool_use_id)
      ? { decision: 'allow', reason: 'confirmed in the push-gate dialog' }
      : next(e),
  )
}
