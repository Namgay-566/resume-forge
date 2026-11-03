import type { DashboardResume, DashboardSummary, ScorePoint } from '@/features/roadmap/types'

export function greeting(now: Date = new Date()): string {
  const hour = now.getHours()
  if (hour < 5) return 'Working late'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function firstName(name: string | undefined): string {
  return name?.trim().split(/\s+/)[0] ?? ''
}

/** The one-line motivational status under the greeting. Always true to the data. */
export function statusLine(data: DashboardSummary): string {
  if (data.resume_count === 0) return 'Let’s start with your resume. Everything else builds on it.'
  if (!data.role || data.readiness === null) return 'Choose a target role to see how ready you are for it.'
  const r = data.readiness
  const lead = `You’re ${r}% ready for ${data.role.name}.`
  if (r >= 85) return `${lead} Keep your proof fresh and tailor for each job.`
  if (r >= 60) return `${lead} A few verified skills to go.`
  return `${lead} Every skill you prove moves this up.`
}

export interface Band {
  label: string
  tone: 'success' | 'warning' | 'danger'
}

export function atsBand(score: number): Band {
  if (score >= 80) return { label: 'Strong', tone: 'success' }
  if (score >= 60) return { label: 'Good start', tone: 'warning' }
  return { label: 'Needs work', tone: 'danger' }
}

export function readinessBand(score: number): Band {
  if (score >= 85) return { label: 'Job-ready', tone: 'success' }
  if (score >= 60) return { label: 'Almost there', tone: 'warning' }
  return { label: 'Building up', tone: 'danger' }
}

/** Change since the previous point in a history, or null with fewer than two points. */
export function lastDelta(history: ScorePoint[]): number | null {
  if (history.length < 2) return null
  return history[history.length - 1].score - history[history.length - 2].score
}

/** The resume the dashboard focuses on (the one the roadmap and next action are for). */
export function focusResume(data: DashboardSummary): DashboardResume | null {
  return data.resumes.find((r) => r.id === data.resume_id) ?? data.resumes[0] ?? null
}
