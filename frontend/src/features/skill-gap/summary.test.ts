import { describe, expect, it } from 'vitest'

import { gapSummary } from './summary'
import type { SkillGapReport } from './types'

const report = (over: Partial<SkillGapReport>): SkillGapReport => ({
  resume_id: 'r',
  role: { id: 'x', name: 'Full Stack Developer', slug: 'fs' },
  readiness: 56,
  skills: [],
  counts: { present_verified: 2, present_unverified: 3, inferred: 1, missing: 2 },
  missing_critical: ['Git', 'HTML/CSS'],
  ai_status: 'ok',
  ...over,
})

describe('gapSummary', () => {
  it('names the missing critical skills', () => {
    expect(gapSummary(report({}))).toBe('You’re 56% ready for Full Stack Developer. 2 critical skills are missing: Git and HTML/CSS.')
    expect(gapSummary(report({ missing_critical: ['Git'] }))).toMatch(/1 critical skill is missing: Git\.$/)
  })

  it('moves on to the next goal once critical gaps are closed', () => {
    expect(gapSummary(report({ missing_critical: [] }))).toMatch(/No critical gaps\. Close the remaining 2/)
    const proveOnly = report({ missing_critical: [], counts: { present_verified: 2, present_unverified: 3, inferred: 1, missing: 0 } })
    expect(gapSummary(proveOnly)).toMatch(/Prove 4 more skills to reach 100%/)
  })
})
