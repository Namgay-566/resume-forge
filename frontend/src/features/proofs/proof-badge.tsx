import { ProofStatusBadge } from './proof-status'
import { PROOF_TYPES } from './proof-types'
import { isRunning, type Proof } from './types'
import { VerificationBadge } from './verification-level'

/** Finished proofs show their verification level; running or rejected ones show the status. */
export function ProofBadge({ proof }: { proof: Pick<Proof, 'status' | 'verification_level'> }) {
  if (!isRunning(proof.status) && proof.verification_level) {
    return <VerificationBadge level={proof.verification_level} />
  }
  return <ProofStatusBadge status={proof.status} />
}

export function proofTitle(proof: Pick<Proof, 'type' | 'url' | 'file_name'>): string {
  // Uploads are named after their file (a licence's url is its register link).
  if (PROOF_TYPES[proof.type].input === 'upload') return proof.file_name ?? PROOF_TYPES[proof.type].label
  if (proof.type === 'github_repo') return proof.url?.replace('https://github.com/', '') ?? 'Repository'
  return proof.url?.replace(/^https?:\/\//, '').replace(/\/$/, '') ?? PROOF_TYPES[proof.type].label
}
