// Mirrors backend/app/schemas/resume_data.py and resume.py.

export type ResumeType = 'resume' | 'cv'
export type ResumeTemplate = 'classic' | 'modern_minimal' | 'compact' | 'conservative' | 'professional' | 'academic'

export interface PersonalInfo {
  full_name: string
  headline: string
  email: string | null
  phone: string | null
  location: string | null
  /** LinkedIn, GitHub, Behance, ORCID, a personal site... printed after the contact details. */
  profile_links: ProfileLink[]
}

export interface ProfileLink {
  label: string
  url: string
}

interface DateRange {
  start_date: string | null
  end_date: string | null
  is_current: boolean
}

export interface ExperienceItem extends DateRange {
  company: string
  title: string
  location: string | null
  bullets: string[]
  tools_and_skills: string[]
}

export interface EducationItem extends DateRange {
  institution: string
  degree: string
  field_of_study: string | null
  grade: string | null
  bullets: string[]
}

export interface ProjectItem {
  name: string
  description: string
  bullets: string[]
  tools_and_skills: string[]
  link: string | null
  proof_id: string | null
}

export interface ResumeSkill {
  name: string
  skill_id: string | null
  proof_id: string | null
}

export interface CertificationItem {
  name: string
  issuer: string | null
  issue_date: string | null
  credential_id: string | null
  credential_url: string | null
  proof_id: string | null
}

/** Core kinds keep their content in dedicated ResumeData fields; the rest in `entries`. */
export const CORE_KINDS = ['summary', 'experience', 'education', 'skills', 'projects', 'certifications', 'achievements'] as const
export type CoreKind = (typeof CORE_KINDS)[number]
export const SECTION_KINDS = [
  ...CORE_KINDS,
  'clinical_experience',
  'teaching_experience',
  'internships',
  'volunteer',
  'research',
  'publications',
  'conferences',
  'portfolio',
  'training',
  'memberships',
  'awards',
  'languages',
  'extracurriculars',
  'custom',
] as const
export type SectionKind = (typeof SECTION_KINDS)[number]

export const isCoreKind = (kind: SectionKind): kind is CoreKind => (CORE_KINDS as readonly string[]).includes(kind)

/** One entry in a non-core section (a placement, publication, award, language...). */
export interface SectionItem {
  title: string
  organization: string
  location: string | null
  start_date: string | null
  end_date: string | null
  is_current: boolean
  description: string
  bullets: string[]
  link: string | null
  proof_id: string | null
}

/** A section as the user arranged it. The order of `ResumeData.sections` is the print order. */
export interface SectionConfig {
  /** The kind, or "custom-<random>" for custom sections. */
  id: string
  kind: SectionKind
  /** The user's heading; null uses the standard one. */
  title: string | null
  entries: SectionItem[]
}

export interface ResumeData {
  personal_info: PersonalInfo
  summary: string
  experience: ExperienceItem[]
  education: EducationItem[]
  projects: ProjectItem[]
  skills: ResumeSkill[]
  certifications: CertificationItem[]
  achievements: string[]
  show_verified_skills: boolean
  sections: SectionConfig[]
}

export type ExperienceLevel = 'student' | 'entry' | 'mid' | 'senior' | 'career_changer'

export interface ResumeSummary {
  id: string
  title: string
  type: ResumeType
  template: ResumeTemplate
  target_role: { id: string; name: string; slug: string; source: 'curated' | 'ai_generated' } | null
  experience_level: ExperienceLevel | null
  ats_score: number | null
  created_at: string
  updated_at: string
}

export interface Resume extends ResumeSummary {
  data: ResumeData
}

export interface ResumeCreate {
  title: string
  type: ResumeType
  target_role_id: string | null
  experience_level?: ExperienceLevel | null
}

export interface ResumeUpdate {
  title?: string
  type?: ResumeType
  template?: ResumeTemplate
  target_role_id?: string | null
  experience_level?: ExperienceLevel | null
  data?: ResumeData
}

export interface ResumeImportResult {
  resume: Resume
  matched_skills: string[]
  unmatched_skills: string[]
}

/** Passed to the editor via router state after an import. */
export interface ImportedState {
  imported: { fileName: string; matchedSkills: string[]; unmatchedSkills: string[] }
}
