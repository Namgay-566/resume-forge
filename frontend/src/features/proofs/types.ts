// Mirrors backend/app/schemas/proof.py and proof_report.py.

export type ProofStatus = 'pending' | 'analyzing' | 'verified' | 'rejected' | 'needs_more'

export type ProofType =
  | 'github_repo'
  | 'live_link'
  | 'certificate'
  | 'professional_license'
  | 'portfolio_link'
  | 'work_sample'
  | 'publication'
  | 'reference_letter'
  | 'experience_letter'
  | 'referee_confirmation'

export interface SkillRef {
  id: string
  name: string
  slug: string
}

export interface ProofCheck {
  id: string
  status: 'pass' | 'warn' | 'fail'
  title: string
  detail: string
  gate: boolean
}

export interface RepoFacts {
  full_name: string
  url: string
  description: string | null
  default_branch: string
  fork: boolean
  parent: string | null
  ahead_of_parent: number | null
  stars: number
  languages: Record<string, number>
  commit_count: number
  commit_days: number
  contributors: { login: string; commits: number }[]
  file_count: number
  has_readme: boolean
  has_tests: boolean
  has_ci: boolean
  has_docker: boolean
  key_files: string[]
  sampled_files: string[]
}

export type VerificationLevel = 'verified' | 'partially_verified' | 'self_reported'

export interface CertificateInfo {
  filename: string
  content_type: string
  text_source: 'pdf_text' | 'vision' | null
  is_certificate: boolean
  issuer: string | null
  recipient_name: string | null
  course_name: string | null
  issue_date: string | null
  credential_id: string | null
  verification_url: string | null
  name_match: { status: 'match' | 'partial' | 'mismatch' | 'missing'; detail: string } | null
  url_check: {
    url: string
    final_url: string | null
    status_code: number | null
    reachable: boolean
    on_trusted_domain: boolean
    details_on_page: boolean
    detail: string
  } | null
  mapped_skills: string[]
}

export interface LiveLinkInfo {
  url: string
  final_url: string | null
  status_code: number | null
  reachable: boolean
  https: boolean
  response_ms: number | null
  title: string
  description: string
  site_name: string
  linked_repo: string | null
  linked_repo_verified: boolean
  connection: string | null
}

export type NameMatch = { status: 'match' | 'partial' | 'mismatch' | 'missing'; detail: string }
export type UrlCheck = NonNullable<CertificateInfo['url_check']>

export interface LicenseInfo {
  is_license: boolean
  license_type: string | null
  holder_name: string | null
  license_number: string | null
  issuing_body: string | null
  jurisdiction: string | null
  issue_date: string | null
  expiry_date: string | null
  register_url: string | null
  register_source: 'user' | 'document' | null
  name_match: NameMatch | null
  register_check: UrlCheck | null
  expired: boolean
  expires_soon: boolean
  expiry_detail: string
  mapped_skills: string[]
}

export interface PortfolioInfo {
  url: string
  final_url: string | null
  status_code: number | null
  reachable: boolean
  https: boolean
  title: string
  description: string
  site_name: string
  platform: string | null
  name_on_page: boolean
  text_chars: number
}

export interface WorkSampleInfo {
  is_work_sample: boolean
  kind: string | null
  text_chars: number
}

export interface PublicationInfo {
  input: string
  doi: string | null
  url: string | null
  source: 'crossref' | 'page' | null
  registered: boolean
  title: string | null
  venue: string | null
  published: string | null
  authors: string[]
  author_match: NameMatch | null
  matched_author: string | null
}

export interface LetterInfo {
  is_letter: boolean
  letter_kind: 'reference' | 'experience' | 'recommendation' | 'other' | null
  writer_name: string | null
  writer_title: string | null
  organization: string | null
  date: string | null
  subject_name: string | null
  relationship: string | null
  has_contact_details: boolean
  name_match: NameMatch | null
  skills_mentioned: { name: string; quote: string }[]
}

export interface ProofReport {
  repo: RepoFacts | null
  ownership: { status: 'confirmed' | 'failed' | 'unknown'; detail: string } | null
  checks: ProofCheck[]
  skills: { skill_id: string; name: string; verdict: 'demonstrated' | 'partially' | 'not_demonstrated'; evidence: string[] }[]
  summary: string
  code_quality: string[]
  red_flags: string[]
  suggestions: string[]
  strengths: string[]
  ai_score: number | null
  ai_status: 'ok' | 'unavailable' | 'failed' | 'skipped'
  certificate: CertificateInfo | null
  live: LiveLinkInfo | null
  upload: { filename: string; content_type: string; text_source: string | null } | null
  license: LicenseInfo | null
  portfolio: PortfolioInfo | null
  work_sample: WorkSampleInfo | null
  publication: PublicationInfo | null
  letter: LetterInfo | null
  /** Who the AI reviewed as, e.g. "a senior nurse and clinical educator". */
  reviewer: string | null
  verification_level: VerificationLevel | null
  decision: string
  error: string | null
  analyzed_at: string | null
}

export interface Proof {
  id: string
  type: ProofType
  url: string | null
  status: ProofStatus
  score: number | null
  skills: SkillRef[]
  verification_level: VerificationLevel | null
  decision: string
  linked_proof_id: string | null
  file_name: string | null
  /** While running: the step the analysis is on (see analysis-progress.tsx). */
  progress: string | null
  created_at: string
}

export interface ProofDetail extends Proof {
  report: ProofReport | null
}

export interface CatalogSkill extends SkillRef {
  category: string
  /** Proof types that suit the skill, best first. */
  proof_types: ProofType[]
}

export const isRunning = (status: ProofStatus) => status === 'pending' || status === 'analyzing'
