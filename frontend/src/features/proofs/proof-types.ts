import { BadgeCheck, BookOpen, FileBadge, FileText, FolderGit2, Images, Link2, Mail, MessageSquareQuote, ScrollText, type LucideIcon } from 'lucide-react'

import type { ProofType, VerificationLevel } from './types'

export interface ProofTypeMeta {
  label: string
  /** For "Prove it with …". */
  short: string
  /** Button label, e.g. "Upload licence". */
  action: string
  icon: LucideIcon
  /** Submitted as a file, as a link, or the user can choose. */
  input: 'upload' | 'link' | 'both'
  /** One line on what we do with it. */
  how: string
  /** The best level this kind of proof can honestly reach. */
  ceiling: VerificationLevel
  /** Why it can't go higher (when it can't reach "verified"). */
  ceilingWhy?: string
  /** Must the user say which skills it shows? */
  skills: 'required' | 'optional' | 'none'
  accept?: string
  formats?: string
}

const DOCS = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png'
const DOCS_AND_WORD = `${DOCS},.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document`

// Mirrors the backend analyses (services/proofs). Order = how they're offered.
export const PROOF_TYPES: Record<ProofType, ProofTypeMeta> = {
  professional_license: {
    action: 'Add licence', label: 'Licence or registration', short: 'a licence', icon: BadgeCheck, input: 'both',
    how: 'We read the licence number, issuing body and expiry date. Upload the file or link to your public register entry.',
    ceiling: 'verified', skills: 'optional', accept: DOCS, formats: 'PDF, JPG or PNG',
  },
  certificate: {
    action: 'Add certificate', label: 'Certificate', short: 'a certificate', icon: FileBadge, input: 'both',
    how: 'Upload the file, or paste a link to the verification page. We check the name and follow the link.',
    ceiling: 'verified', skills: 'optional', accept: DOCS, formats: 'PDF, JPG or PNG',
  },
  work_sample: {
    action: 'Upload work sample', label: 'Work sample', short: 'a work sample', icon: FileText, input: 'upload',
    how: 'A plan, report, design, lesson plan or photo of finished work, reviewed by an experienced professional in your field.',
    ceiling: 'self_reported', ceilingWhy: 'we can’t confirm you produced an uploaded file',
    skills: 'required', accept: DOCS_AND_WORD, formats: 'PDF, Word, JPG or PNG',
  },
  portfolio_link: {
    action: 'Add portfolio link', label: 'Portfolio link', short: 'a portfolio link', icon: Images, input: 'link',
    how: 'Behance, Dribbble, published writing or your own site. We check it’s live, look for your name and review the work.',
    ceiling: 'partially_verified', ceilingWhy: 'a public page can’t prove who made the work',
    skills: 'required',
  },
  publication: {
    action: 'Add publication', label: 'Publication', short: 'a publication', icon: BookOpen, input: 'link',
    how: 'A DOI or link. We look it up in the DOI registry and check your name is among the authors.',
    ceiling: 'verified', skills: 'required',
  },
  reference_letter: {
    action: 'Upload reference', label: 'Reference letter', short: 'a reference letter', icon: Mail, input: 'upload',
    how: 'We note who wrote it, their organisation and which skills it mentions.',
    ceiling: 'self_reported', ceilingWhy: 'we can’t contact the writer (employers can)',
    skills: 'optional', accept: DOCS_AND_WORD, formats: 'PDF, Word, JPG or PNG',
  },
  experience_letter: {
    action: 'Upload experience letter', label: 'Experience letter', short: 'an experience letter', icon: ScrollText, input: 'upload',
    how: 'A letter from an employer confirming your role, dates and duties.',
    ceiling: 'self_reported', ceilingWhy: 'we can’t contact the employer (employers can)',
    skills: 'optional', accept: DOCS_AND_WORD, formats: 'PDF, Word, JPG or PNG',
  },
  github_repo: {
    action: 'Add GitHub repo', label: 'GitHub repository', short: 'a GitHub repo', icon: FolderGit2, input: 'link',
    how: 'For technical skills: we check it’s yours, read the commit history and review the code.',
    ceiling: 'verified', skills: 'required',
  },
  live_link: {
    action: 'Add live site', label: 'Live website', short: 'a live site', icon: Link2, input: 'link',
    how: 'A site you built, linked to its GitHub repository proof.',
    ceiling: 'verified', skills: 'none',
  },
  referee_confirmation: {
    action: 'Ask a referee', label: 'Referee confirmation', short: 'a referee confirmation', icon: MessageSquareQuote, input: 'link',
    how: 'Ask a former manager or colleague to confirm your work.',
    ceiling: 'verified', skills: 'required',
  },
}

export const PROOF_TYPE_ORDER = Object.keys(PROOF_TYPES) as ProofType[]

export const isProofType = (value: string | null): value is ProofType => value !== null && value in PROOF_TYPES