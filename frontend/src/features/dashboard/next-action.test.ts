import { describe, expect, it } from 'vitest'

import type { NextAction } from '@/features/roadmap/types'

import { nextActionHref } from './next-action'

const action = (kind: NextAction['kind']): NextAction => ({
  kind,
  title: '',
  detail: '',
  resume_id: 'r1',
  skill_id: 's1',
  skill_slug: 'git',
})

describe('nextActionHref', () => {
  it.each([
    ['create_resume', '/resumes'],
    ['choose_role', '/resumes/r1'],
    ['close_gap', '/roadmap?resume=r1#roadmap-git'],
    ['continue_skill', '/roadmap?resume=r1#roadmap-git'],
    ['prove_skill', '/proof-vault?skill=git'],
    ['run_ats', '/resumes/r1?ats=open'],
    ['improve_ats', '/resumes/r1?ats=open'],
    ['all_set', '/resumes/r1'],
  ] as const)('%s -> %s', (kind, href) => {
    expect(nextActionHref(action(kind))).toBe(href)
  })
})
