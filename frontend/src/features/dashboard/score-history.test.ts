import { describe, expect, it } from 'vitest'

import { buildHistory } from './score-history'

const DAY = 86_400_000
const t0 = Date.parse('2026-09-01T10:00:00Z')
const iso = (days: number) => new Date(t0 + days * DAY).toISOString()

describe('buildHistory', () => {
  it('merges both series on one timeline, carrying scores forward to now', () => {
    const rows = buildHistory(
      [{ at: iso(0), score: 46 }, { at: iso(7), score: 81 }],
      [{ at: iso(3), score: 15 }],
      t0 + 10 * DAY,
    )

    expect(rows.map((r) => [r.ats, r.readiness, r.atsPoint, r.readinessPoint])).toEqual([
      [46, null, true, false], // readiness not measured yet: no line before its first point
      [46, 15, false, true],
      [81, 15, true, false],
      [81, 15, false, false], // "now": extends the lines, no marker
    ])
    expect(rows.at(-1)?.t).toBe(t0 + 10 * DAY)
  })

  it('gives a single check some width and handles no data', () => {
    const rows = buildHistory([{ at: iso(0), score: 70 }], [], t0)
    expect(rows).toHaveLength(2)
    expect(rows[1].t - rows[0].t).toBe(DAY)
    expect(buildHistory([], [])).toEqual([])
  })
})
