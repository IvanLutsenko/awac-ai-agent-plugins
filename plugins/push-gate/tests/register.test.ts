import { expect, test } from 'claude-code/testing'

import { needsConfirm, repoDir, warnings } from '../hooks/register'

test('needsConfirm errs toward asking', async () => {
  for (const command of [
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
    'glab mr create --fill --push',
    'gh pr create --fill',
    'claude --safe-mode -p "do it"',
    'codex exec --dangerously-bypass-approvals-and-sandbox "x"',
  ]) {
    expect(needsConfirm(command)).toBe(true)
  }
  for (const command of ['git status', 'git pushx', 'npm push', 'glab mr list', 'gh pr view 1', 'claude -p "hi"']) {
    expect(needsConfirm(command)).toBe(false)
  }
})

test('warnings mark force and protected branches', async () => {
  expect(warnings('git push --force origin x')).toEqual(['FORCE'])
  expect(warnings('git push -f origin x')).toEqual(['FORCE'])
  expect(warnings('git push origin +x')).toEqual(['FORCE'])
  expect(warnings('git push --force-with-lease=x origin x')).toEqual(['FORCE'])
  expect(warnings('git push origin release')).toEqual(['защищённая ветка'])
  expect(warnings('git push', 'main')).toEqual(['защищённая ветка'])
  expect(warnings('git push --follow-tags origin feature/x', 'feature/x')).toEqual([])
})

test('repoDir reads git -C in every quoting', async () => {
  expect(repoDir('git -C /a/b push')).toBe('/a/b')
  expect(repoDir('git -C "/a b" push')).toBe('/a b')
  expect(repoDir("git -C '/a b' push")).toBe('/a b')
  expect(repoDir('git push')).toBeUndefined()
})
