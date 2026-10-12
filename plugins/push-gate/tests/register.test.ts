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
    'git -C /a \\\n  push',
    'git "push"',
    'git -P -c http.x=y --no-pager push',
    'git --git-dir=/a/.git push',
    'git -c alias.p=push p',
    'git status; git push origin x',
    'glab mr create --fill --push',
    'gh pr create --fill',
    'claude --safe-mode -p "do it"',
    'codex exec --dangerously-bypass-approvals-and-sandbox "x"',
  ]) {
    expect(needsConfirm(command)).toBe(true)
  }
  for (const command of [
    'git status',
    'git pushx',
    'npm push',
    'glab mr list',
    'gh pr view 1',
    'claude -p "hi"',
    'git log --grep push',
    'git commit -m "push fix"',
    'git -C /a log -- core/push/push-impl',
    'git-push-helper',
    'git log | grep -c push',
    SCREENSHOT,
  ]) {
    expect(needsConfirm(command)).toBe(false)
  }
})

// A read-only probe that the old words-anywhere rule took for a protected push.
const SCREENSHOT =
  'R=/var/folders/T/combined-review-XXXXXX.WO8; P=core/push/push-impl/src/main/java/kz/push_impl; ' +
  'git -C $R merge-base --is-ancestor origin/feature/TRSC-1987 origin/release; echo anc=$?; ' +
  "grep -n 'MessagingServiceImpl(' $R/$P/di/PushKoinModule.kt; " +
  "grep -rn 'MessagingServiceImpl(' $R/core/push --include=*.kt | grep -v 'class '"

test('warnings mark force and protected branches', async () => {
  expect(warnings('git push --force origin x')).toEqual(['FORCE'])
  expect(warnings('git push -f origin x')).toEqual(['FORCE'])
  expect(warnings('git push origin +x')).toEqual(['FORCE'])
  expect(warnings('git push --force-with-lease=x origin x')).toEqual(['FORCE'])
  expect(warnings('git push origin release')).toEqual(['защищённая ветка'])
  expect(warnings('git push', 'main')).toEqual(['защищённая ветка'])
  expect(warnings('git push --follow-tags origin feature/x', 'feature/x')).toEqual([])
  expect(warnings('git merge-base HEAD origin/release; rm -rf /tmp/x; git push origin feature/x', 'feature/x')).toEqual([])
})

test('repoDir reads git -C in every quoting', async () => {
  expect(repoDir('git -C /a/b push')).toBe('/a/b')
  expect(repoDir('git -C "/a b" push')).toBe('/a b')
  expect(repoDir("git -C '/a b' push")).toBe('/a b')
  expect(repoDir('git push')).toBeUndefined()
  expect(repoDir('git -C /x log; git -C /a/b push')).toBe('/a/b')
  expect(repoDir('R=/a/b; git -C "$R" push')).toBe('/a/b')
  expect(repoDir("R='/a b' && git -C \"${R}\" push")).toBe('/a b')
  expect(repoDir('git -C $UNSET push')).toBe('$UNSET')
})
