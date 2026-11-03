// Mirrors backend/app/schemas/ats.py.

export type CategoryKey = 'formatting' | 'keywords' | 'impact' | 'completeness'
export type SectionKey =
  | 'personal_info'
  | 'summary'
  | 'experience'
  | 'education'
  | 'projects'
  | 'skills'
  | 'certifications'
  | 'achievements'

export interface Location {
  /** A SectionKey, or the id of any other section ("clinical_experience", "custom-x1"). */
  section: SectionKey | (string & {})
  item_index: number | null
  /** The section's heading, when it isn't a standard SectionKey. */
  label?: string | null
}

/** "Experience", "Clinical Experience", "Hobbies"... */
export function locationSection(location: Location): string {
  return location.label || SECTION_LABELS[location.section as SectionKey] || 'Section'
}

export interface CheckResult {
  id: string
  category: CategoryKey
  status: 'pass' | 'warn' | 'fail'
  title: string
  detail: string
  weight: number
  location: Location | null
  points_lost: number
}

export interface KeywordHit {
  keyword: string
  importance: 'required' | 'preferred'
  weight: number
  matched_as: string | null
}

export interface KeywordReport {
  source: 'job_description' | 'target_role' | null
  extraction: 'ai' | 'catalog' | 'target_role' | null
  matched: KeywordHit[]
  missing: KeywordHit[]
}

export interface CategoryScore {
  key: CategoryKey
  label: string
  score: number | null
  weight: number
}

export interface SectionFeedback {
  section: SectionKey
  rating: 'strong' | 'ok' | 'weak'
  feedback: string
  suggestions: string[]
}

export interface Fix {
  priority: number
  severity: 'high' | 'medium' | 'low'
  title: string
  detail: string
  source: 'check' | 'keywords' | 'ai'
  location: Location | null
  points: number | null
}

export interface AtsReport {
  score: number
  categories: CategoryScore[]
  checks: CheckResult[]
  keywords: KeywordReport
  ai_review: { overall: string; sections: SectionFeedback[] } | null
  ai_status: 'ok' | 'unavailable' | 'failed' | 'skipped' | 'rate_limited'
  fixes: Fix[]
}

export interface AtsAnalysis {
  id: string
  resume_id: string
  job_description: string | null
  score: number
  report: AtsReport
  created_at: string
  previous: { score: number; categories: CategoryScore[]; created_at: string } | null
}

export const SECTION_LABELS: Record<SectionKey, string> = {
  personal_info: 'Personal info',
  summary: 'Summary',
  experience: 'Experience',
  education: 'Education',
  projects: 'Projects',
  skills: 'Skills',
  certifications: 'Licenses & Certifications',
  achievements: 'Achievements',
}
