import { describe, expect, it } from 'vitest'

import { groupSkills } from './grouping'
import type { Importance, RoleSkillGap } from './types'

const skill = (name: string, importance: Importance, group: string, sort_order: number): RoleSkillGap => ({
  skill_id: name,
  name,
  slug: name,
  category: 'clinical',
  group: { slug: `${group}-${sort_order}`, name: group, sort_order },
  importance,
  weight: 1,
  status: 'missing',
  evidence: [],
  verification_status: null,
  proof_types: [],
})

const NURSE = [
  skill('Patient Education', 'nice_to_have', 'Patient care', 2),
  skill('Nursing License', 'critical', 'Credentials', 0),
  skill('Patient Assessment', 'important', 'Clinical skills', 1),
  skill('Infection Control', 'critical', 'Clinical skills', 1),
  skill('Basic Life Support', 'critical', 'Credentials', 100),
  skill('Teamwork', 'important', 'Soft skills', 101),
]

describe('groupSkills', () => {
  it('groups by the field’s own categories, in seed order', () => {
    const sections = groupSkills(NURSE, 'category')
    expect(sections.map((s) => s.title)).toEqual(['Credentials', 'Clinical skills', 'Patient care', 'Soft skills'])
  })

  it('merges same-named groups and puts critical skills first', () => {
    const [credentials, clinical] = groupSkills(NURSE, 'category')
    expect(credentials.skills.map((s) => s.name)).toEqual(['Nursing License', 'Basic Life Support'])
    expect(credentials.blurb).toBe('2 skills · 2 critical')
    expect(clinical.skills.map((s) => s.name)).toEqual(['Infection Control', 'Patient Assessment'])
    expect(groupSkills(NURSE, 'category')[2].blurb).toBe('1 skill')
  })

  it('can still group by importance, skipping empty levels', () => {
    const sections = groupSkills(NURSE.filter((s) => s.importance !== 'important'), 'importance')
    expect(sections.map((s) => s.title)).toEqual(['Critical', 'Nice to have'])
  })

  it('gives each section a unique, id-safe key', () => {
    const keys = groupSkills([skill('A', 'critical', 'CRM & sales tools', 3)], 'category').map((s) => s.key)
    expect(keys).toEqual(['cat-crm-sales-tools'])
  })
})
