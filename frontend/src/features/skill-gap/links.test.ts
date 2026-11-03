import { describe, expect, it } from 'vitest'

import { proofAction, proofHint, proofLink } from './links'

const licence = { slug: 'nursing-license', name: 'Nursing License', proof_types: ['professional_license', 'certificate'] as const }
const excel = { slug: 'spreadsheets', name: 'Spreadsheets', proof_types: ['work_sample', 'certificate'] as const }

describe('proof suggestions per skill', () => {
  it('links to the vault with the best proof type preselected', () => {
    const url = new URL(proofLink({ ...licence, proof_types: [...licence.proof_types] }, 'r1'), 'https://x')

    expect(url.pathname).toBe('/proof-vault')
    expect(Object.fromEntries(url.searchParams)).toEqual({ skill: 'nursing-license', name: 'Nursing License', resume: 'r1', type: 'professional_license' })
  })

  it('names the right action and alternatives', () => {
    expect(proofAction({ ...licence, proof_types: [...licence.proof_types] })).toBe('Upload licence')
    expect(proofHint({ ...excel, proof_types: [...excel.proof_types] })).toBe('Best proof: work sample, or certificate.')
    expect(proofAction({ slug: 'x', name: 'X', proof_types: [] })).toBe('Upload proof')
  })
})
