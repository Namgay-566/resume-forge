// Mirrors backend/app/schemas/writing.py.
import type { Location } from '@/features/ats/types'

export interface WritingOption {
  text: string
  rationale: string | null
  placeholders: string[]
  replaced_numbers: string[]
}

export type SuggestionKind =
  | 'rewrite_bullet'
  | 'move_bullet_up'
  | 'rewrite_summary'
  | 'feature_skills'
  | 'add_skill'

export interface Suggestion {
  id: string
  kind: SuggestionKind
  location: Location
  reason: string
  before: string | null
  after: string | null
  before_items: string[] | null
  after_items: string[] | null
  placeholders: string[]
}

export interface TailorResult {
  suggestions: Suggestion[]
  gaps: string[]
}
