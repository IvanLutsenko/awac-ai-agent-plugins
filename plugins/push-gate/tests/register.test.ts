import { expect, test } from 'claude-code/testing'

import { isPush, touchesToken } from '../hooks/register'

test('isPush errs toward asking: git and push as words anywhere', async () => {
  for (const push of [
    'git push',
    'git -C /a/b push origin feature/CPT-1',
    'bash -c "git push"',
    '( git push )',
    '/usr/bin/git push',
    'command git push',
    'env git push',
    'git -C "/a b" push',
    'git status\ngit push',
    'git log --grep push',
  ]) {
    expect(isPush(push)).toBe(true)
  }
  for (const other of ['git status', 'git pushx', 'PUSH_OK=1 echo git', 'npm push', 'gitpush']) {
    expect(isPush(other)).toBe(false)
  }
})

test('touchesToken sees the token path in any tool input', async () => {
  expect(touchesToken({ command: 'echo x > ~/.claude/push-gate/token' })).toBe(true)
  expect(touchesToken({ file_path: '/Users/lutse/.claude/push-gate/token', content: 'git push' })).toBe(true)
  expect(touchesToken({ command: 'git status' })).toBe(false)
})
