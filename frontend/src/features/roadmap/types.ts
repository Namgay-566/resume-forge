// Mirrors backend/app/schemas/roadmap.py and project_idea.py.
import type { Importance, LearningResource, SkillStatus } from '@/features/skill-gap/types'

export type PlanStatus = 'not_started' | 'in_progress' | 'done'
export type { ProofType } from '@/features/proofs/types'
import type { ProofType } from '@/features/proofs/types'

export interface ProjectIdea {
  title: string
  summary: string
  steps: string[]
  reviewer_checks: string[]
  est_hours: number
  stretch: string | null
  tailored_for: string | null
  /** The kind of proof it produces and what gets uploaded (missing on older ideas). */
  proof_type?: string | null
  deliverable?: string | null
}

export interface RoadmapItem {
  skill_id: string
  name: string
  slug: string
  category: string
  importance: Importance
  weight: number
  gap_status: SkillStatus
  plan_status: PlanStatus
  resources: LearningResource[]
  /** When there are no curated resources: something to search for. */
  search_phrase: string
  proof: { accepted: ProofType[]; must_include: string[] }
  project: ProjectIdea | null
  hours: { learn: number; project: number; total: number }
}

export interface RoadmapTotals {
  items: number
  done: number
  in_progress: number
  hours_total: number
  hours_remaining: number
}

export interface Roadmap {
  resume_id: string
  role: { id: string; name: string; slug: string }
  readiness: number
  items: RoadmapItem[]
  totals: RoadmapTotals
}

export type NextActionKind =
  | 'create_resume'
  | 'choose_role'
  | 'continue_skill'
  | 'close_gap'
  | 'prove_skill'
  | 'run_ats'
  | 'improve_ats'
  | 'all_set'

export interface NextAction {
  kind: NextActionKind
  title: string
  detail: string
  resume_id: string | null
  skill_id: string | null
  skill_slug: string | null
}

export interface ScorePoint {
  at: string
  score: number
}

export interface DashboardResume {
  id: string
  title: string
  type: 'resume' | 'cv'
  target_role: { id: string; name: string; slug: string } | null
  ats_score: number | null
  readiness: number | null
  updated_at: string
  ats_history: ScorePoint[] // oldest first
  readiness_history: ScorePoint[] // oldest first, current target role only
}

export interface DashboardSummary {
  resume_id: string | null
  resume_title: string | null
  role: { id: string; name: string; slug: string } | null
  readiness: number | null
  ats_score: number | null
  totals: RoadmapTotals | null
  next_up: RoadmapItem | null
  next_action: NextAction
  resumes: DashboardResume[] // most recently edited first
  resume_count: number
}
