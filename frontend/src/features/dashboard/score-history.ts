import type { ScorePoint } from '@/features/roadmap/types'

export interface HistoryRow {
  t: number
  ats: number | null
  readiness: number | null
  /** True where that score was actually measured (a marker); other rows carry it forward. */
  atsPoint: boolean
  readinessPoint: boolean
}

const DAY = 86_400_000

/** Merge both histories onto one timeline. A score holds until the next check, so each row
 * carries the latest value forward, and a final row at `now` extends the lines to today. */
export function buildHistory(ats: ScorePoint[], readiness: ScorePoint[], now: number = Date.now()): HistoryRow[] {
  const a = ats.map((p) => ({ t: Date.parse(p.at), score: p.score }))
  const r = readiness.map((p) => ({ t: Date.parse(p.at), score: p.score }))
  const times = [...new Set([...a, ...r].map((p) => p.t))].sort((x, y) => x - y)
  if (times.length === 0) return []

  const at = (series: { t: number; score: number }[], t: number) => {
    let value: number | null = null
    for (const p of series) if (p.t <= t) value = p.score
    return value
  }
  const rows = times.map((t) => ({
    t,
    ats: at(a, t),
    readiness: at(r, t),
    atsPoint: a.some((p) => p.t === t),
    readinessPoint: r.some((p) => p.t === t),
  }))
  const last = rows[rows.length - 1]
  // At least a day of width, so a single check isn't a dot on the edge.
  const end = Math.max(now, times[0] + DAY)
  if (end > last.t) rows.push({ ...last, t: end, atsPoint: false, readinessPoint: false })
  return rows
}
