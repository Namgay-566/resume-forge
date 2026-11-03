import { PROOF_TYPES } from '@/features/proofs/proof-types'

import type { RoleSkillGap } from './types'

type ProofTarget = Pick<RoleSkillGap, 'slug' | 'name' | 'proof_types'>

/** Proof Vault with the skill and its best proof type preselected (and the resume to come
 * back to). */
export function proofLink(skill: ProofTarget, resumeId: string): string {
  const params = new URLSearchParams({ skill: skill.slug, name: skill.name, resume: resumeId })
  if (skill.proof_types[0]) params.set('type', skill.proof_types[0])
  return `/proof-vault?${params}`
}

/** "Upload licence", "Add portfolio link"... for the skill's best proof type. */
export function proofAction(skill: ProofTarget): string {
  const best = skill.proof_types[0]
  return best ? (PROOF_TYPES[best]?.action ?? 'Upload proof') : 'Upload proof'
}

/** "Best proof: licence or registration, or certificate." */
export function proofHint(skill: ProofTarget): string | null {
  const [first, second] = skill.proof_types
  if (!first) return null
  const names = [first, second]
    .filter(Boolean)
    .map((t) => PROOF_TYPES[t!]?.label?.toLowerCase())
    .filter(Boolean)

  if (names.length === 0) return null
  return `Best proof: ${names.join(', or ')}.`
}