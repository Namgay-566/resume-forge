import type { ExperienceLevel, ResumeTemplate, ResumeType } from '@/features/resumes/types'

export type PageSize = 'a4' | 'letter'
export type Spelling = 'en_us' | 'en_gb'
export type SignInProvider = 'google' | 'linkedin' | 'github'

/** Defaults and choices from Settings (backend UserPreferences). */
export interface UserPreferences {
  default_resume_type: ResumeType
  default_experience_level: ExperienceLevel | null
  /** Null: the template recommended for the resume's field. */
  default_template: ResumeTemplate | null
  page_size: PageSize
  /** Null: follow the spelling already used in the resume. */
  spelling: Spelling | null
  email_proof_updates: boolean
}

export interface User {
  id: string
  email: string
  name: string
  github_username: string | null
  /** Signed in with LinkedIn; its profile URL once known (LinkedIn rarely shares it). */
  linkedin_connected: boolean
  linkedin_url: string | null
  has_password: boolean
  github_connected: boolean
  google_connected: boolean
  preferences: UserPreferences
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}
