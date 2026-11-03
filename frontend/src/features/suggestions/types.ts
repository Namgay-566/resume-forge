// Mirrors backend/app/schemas/suggestions.py.
import type { ProofType, VerificationLevel } from '@/features/proofs/types'
import type { CertificationItem, ProjectItem, SectionItem, SectionKind } from '@/features/resumes/types'

export interface ProofLink {
  proof_id: string
  type: ProofType
  url: string | null
  display_url: string | null
  verified: boolean
  level: VerificationLevel | null
}

/** Where an add_bullet suggestion goes: a job, or an entry in a section like Clinical Experience. */
export interface BulletTarget {
  section_id: string
  item_index: number
  item_title: string
  label: string
}

export interface ResumeSuggestion {
  id: string
  kind: 'add_skill' | 'link_skill_proof' | 'add_project' | 'add_certification' | 'add_section_entry' | 'add_bullet'
  title: string
  detail: string
  proof_id: string
  skill_id: string | null
  skill_name: string | null
  skill_index: number | null
  resume_skill_name: string | null
  /** add_project: a repo to draft from, or a ready entry (from a work sample). */
  repo_url: string | null
  project: ProjectItem | null
  certification: CertificationItem | null
  /** add_section_entry: a prefilled entry for this section (link as plain text). */
  section_kind: SectionKind | null
  section_heading: string | null
  entry: SectionItem | null
  /** add_bullet: a bullet for an existing entry. */
  bullet: string | null
  target: BulletTarget | null
  level: VerificationLevel | null
}

export interface ProjectDraft {
  name: string
  description: string
  bullets: string[]
  tools_and_skills: string[]
  link: string
}

export type ProofLinks = Record<string, ProofLink>
