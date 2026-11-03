import { describe, expect, it } from 'vitest'

import type { DashboardSummary } from '@/features/roadmap/types'

import { atsBand, firstName, greeting, lastDelta, readinessBand, statusLine } from './status'

const base = {
  resume_id: 'r1',
  resume_title: 'Main',
  role: { id: 'x', name: 'Full Stack Developer', slug: 'fs' },
  readiness: 72,
  ats_score: 81,
  totals: null,
  next_up: null,
  next_action: { kind: 'close_gap', title: '', detail: '', resume_id: 'r1', skill_id: null, skill_slug: null },
  resumes: [],
  resume_count: 1,
} satisfies DashboardSummary

describe('dashboard status', () => {
  it('says how ready you are, with an encouraging next line', () => {
    expect(statusLine(base)).toBe('You’re 72% ready for Full Stack Developer. A few verified skills to go.')
    expect(statusLine({ ...base, readiness: 30 })).toMatch(/Every skill you prove moves this up/)
    expect(statusLine({ ...base, readiness: 90 })).toMatch(/Keep your proof fresh/)
  })

  it('guides first steps when there is nothing to measure yet', () => {
    expect(statusLine({ ...base, resume_count: 0 })).toMatch(/start with your resume/)
    expect(statusLine({ ...base, role: null, readiness: null })).toMatch(/Choose a target role/)
  })

  it('bands, deltas, names and greetings', () => {
    expect(atsBand(84).label).toBe('Strong')
    expect(atsBand(61).tone).toBe('warning')
    expect(readinessBand(40).label).toBe('Building up')
    expect(lastDelta([{ at: 'a', score: 50 }, { at: 'b', score: 58 }])).toBe(8)
    expect(lastDelta([{ at: 'a', score: 50 }])).toBeNull()
    expect(firstName('  Ada   Lovelace ')).toBe('Ada')
    expect(greeting(new Date(2026, 0, 1, 9))).toBe('Good morning')
    expect(greeting(new Date(2026, 0, 1, 20))).toBe('Good evening')
  })
})
