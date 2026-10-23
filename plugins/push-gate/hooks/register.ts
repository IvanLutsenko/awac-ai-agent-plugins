import type { EngineInterface, Register } from 'claude-code'

const PUSH = 'Пушить'
const MAX_SHOWN = 2000
const PROTECTED = /\b(release|master|main)\b/

// git, its global options (-C <path>, -c <k=v>, --git-dir=…, -P), then push as
// the subcommand: `push` as a path segment (core/push/…) or a word in a grep
// pattern or a commit message is not a push. The shape stays wide: bash -c,
// subshells, /usr/bin/git, env prefixes, quoted -C paths, a push on a later
// line or after a backslash-newline. Group 1: global options, group 2: the
// push's own arguments up to the end of its command.
// Mirror: ~/.claude/hooks/bash-footgun-guard.sh (PreToolUse deny); keep in step.
const GIT_PUSH =
  /(?:^|[^\w.-])git((?:\s+(?:-C|-c|--git-dir|--work-tree|--namespace)(?:\s+|=)(?:"[^"]*"|'[^']*'|\S+)|\s+--?[\w-]+(?:=\S*)?)*)\s+["']?push(?=$|[\s;&|)"'])([^;&|\n]*)/

const unfold = (command: string) => command.replace(/\\\n/g, ' ')

// Also a push hidden in an alias (`git -c alias.p=push p`), the tools that push
// on their own, and child agents started with their guards off.
export function needsConfirm(command: string): boolean {
  const c = unfold(command)
  return (
    GIT_PUSH.test(c) ||
    /(?:^|[^\w.-])git\s(?:[^;&|\n]*\s)?-c\s*alias\./.test(c) ||
    /\bglab\b[^\n]*--push\b/.test(c) ||
    /\bgh\s+pr\s+create\b/.test(c) ||
    /\b(claude|codex|pi)\b[^\n]*--(safe-mode|bare|dangerously-[\w-]+)/.test(c)
  )
}

// Only the push's own arguments: `merge-base origin/release` or `rm -rf` in a
// neighbouring command is neither a protected branch nor a force.
export function warnings(command: string, branch?: string): string[] {
  const args = unfold(command).match(GIT_PUSH)?.[2] ?? command
  const marks: string[] = []
  if (/(^|\s)(--force|--force-with-lease|-[a-zA-Z]*f[a-zA-Z]*)(\s|=|$)|\s\+\S/.test(args)) marks.push('FORCE')
  if (PROTECTED.test(args) || (branch !== undefined && PROTECTED.test(branch))) marks.push('защищённая ветка')
  return marks
}

// Where the push runs: the -C path of the push itself, with $VAR / ${VAR} taken
// from a VAR=value earlier in the same command; else the session's directory.
// ponytail: an exported VAR or ~ stays as written and the branch line shows "?".
export function repoDir(command: string): string | undefined {
  const c = unfold(command)
  const m = c.match(GIT_PUSH)?.[1].match(/-C\s+(?:"([^"]+)"|'([^']+)'|(\S+))/)
  const dir = m == null ? undefined : (m[1] ?? m[2] ?? m[3])
  return dir?.replace(/\$\{?(\w+)\}?/g, (raw, name: string) => {
    const a = c.match(new RegExp(`(?:^|[\\s;&(])${name}=(?:"([^"]*)"|'([^']*)'|([^\\s;&|]*))`))
    return a === null ? raw : (a[1] ?? a[2] ?? a[3])
  })
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

// Up to 10 minutes, $.process.run's ceiling: a push over a slow link, gh pr create.
const RUN_MS = 10 * 60 * 1000

// The mod asks in tool.call and, on the click, runs the command itself and
// answers with its output in place of next: PreToolUse and tool.check never
// see a confirmed push, so a PreToolUse guard that denies every push stays
// the backstop for sessions without the mod. Lifting that deny in tool.check
// stopped working once a managed tier hook there began handing the event past
// the user tier (CC 2.1.308). The click is the decision; nothing to forge.
// ponytail: runs in the session's cwd under bash, not the Bash tool's shell;
// a `cd` the model ran earlier in the Bash tool does not carry over.
export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (!needsConfirm(e.command)) return next(e)
    if (e.command.length > MAX_SHOWN) {
      return { deny: `push-gate: the command is longer than ${MAX_SHOWN} characters and cannot be shown whole; split it.` }
    }

    const answer = await $.ui.ask(await question($, e.command), { options: [PUSH, 'Отмена'], header: 'push-gate' })
    if (answer !== PUSH) return { deny: 'The person declined this push in the push-gate dialog.' }

    const run = await $.process.run(['bash', '-c', e.command], { cwd: await $.session.cwd(), timeoutMs: RUN_MS })
    const exit = run.exitCode === 0 ? '' : `${run.stderr === '' ? '' : '\n'}Exit code ${run.exitCode}`
    return { result: { stdout: run.stdout, stderr: run.stderr + exit, interrupted: false } }
  }).catch(($, e, next) =>
    next.called ? next(e) : { deny: 'push-gate could not ask the person or run the push; push refused.' },
  )
}
