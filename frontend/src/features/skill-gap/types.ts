import type { ProofType } from '@/features/proofs/types'

// Mirrors backend/app/schemas/skill_gap.py and learning.py.

export type SkillStatus = 'present_verified' | 'present_unverified' | 'inferred' | 'missing'
export type Importance = 'critical' | 'important' | 'nice_to_have'

export interface Evidence {
  kind: 'verified_proof' | 'profile' | 'skills_section' | 'certification' | 'tools' | 'resume_text' | 'ai_inferred'
  detail: string
}

export interface SkillGroupRef {
  slug: string
  name: string
  sort_order: number
}

export interface RoleSkillGap {
  skill_id: string
  name: string
  slug: string
  category: string
  /** The field-specific display group ("Clinical skills", "CRM & sales tools"...). */
  group: SkillGroupRef
  importance: Importance
  weight: number
  status: SkillStatus
  evidence: Evidence[]
  verification_status: 'unverified' | 'pending' | 'verified' | 'rejected' | null
  /** Kinds of proof that suit this skill, best first. */
  proof_types: ProofType[]
}

export interface SkillGapReport {
  resume_id: string
  role: { id: string; name: string; slug: string; source?: 'curated' | 'ai_generated' }
  readiness: number
  skills: RoleSkillGap[]
  counts: Record<SkillStatus, number>
  missing_critical: string[]
  ai_status: 'ok' | 'cached' | 'skipped' | 'rate_limited' | 'unavailable' | 'failed'
}

export interface LearningResource {
  id: string
  title: string
  provider: string
  url: string
  type: 'course' | 'docs' | 'tutorial' | 'video'
  level: string
  is_free: boolean
  est_hours: string | null
}
