import { describe, expect, it } from 'vitest'

import type { KindSpec, SectionCatalog } from '../sections/api'
import type { ResumeData, SectionConfig, SectionItem } from '../types'
import { buildDocument, orderedSections } from './document'

const base: ResumeData = {
  personal_info: { full_name: 'Priya Shah', headline: '', email: null, phone: null, location: null, profile_links: [] },
  summary: 'Registered nurse.',
  experience: [],
  education: [{ institution: 'City University', degree: 'BSc Nursing', field_of_study: null, grade: null, start_date: null, end_date: '2024-06', is_current: false, bullets: [] }],
  projects: [{ name: 'Falls audit', description: 'Ward audit', bullets: [], tools_and_skills: [], link: null, proof_id: null }],
  skills: [{ name: 'Triage', skill_id: null, proof_id: null }],
  certifications: [],
  achievements: [],
  show_verified_skills: false,
  sections: [],
}

const item = (fields: Partial<SectionItem>): SectionItem => ({
  title: '', organization: '', location: null, start_date: null, end_date: null, is_current: false,
  description: '', bullets: [], link: null, proof_id: null, ...fields,
})
const section = (id: string, fields: Partial<SectionConfig> = {}): SectionConfig => ({
  id, kind: id as SectionConfig['kind'], title: null, entries: [], ...fields,
})
const spec = (fields: Partial<KindSpec>): KindSpec => ({
  kind: 'custom', heading: '', standard_headings: [], hint: null, item_label: 'entry', counts_as_experience: false,
  layout: 'entries', repeatable: false, fields: null, ...fields,
})
const CATALOG: SectionCatalog = {
  clinical_experience: spec({ kind: 'clinical_experience', heading: 'Clinical Experience', fields: { title: { label: 'Role', placeholder: null }, organization: null, location: null, dates: 'range', description: null, bullets: null, link: null } }),
  publications: spec({ kind: 'publications', heading: 'Publications', fields: { title: { label: 'Title', placeholder: null }, organization: null, location: null, dates: 'single', description: null, bullets: null, link: null } }),
  languages: spec({ kind: 'languages', heading: 'Languages', layout: 'inline' }),
}

describe('buildDocument', () => {
  it("follows the user's order and headings", () => {
    const data: ResumeData = {
      ...base,
      sections: [
        section('summary', { title: 'Profile' }),
        section('clinical_experience', {
          entries: [item({ title: 'Student Nurse', organization: "St Mary's", start_date: '2024-01', is_current: true, bullets: ['Monitored vitals'] })],
        }),
        section('education'),
        section('skills'),
        section('languages', { entries: [item({ title: 'Spanish', organization: 'Fluent' }), item({ title: 'Welsh' })] }),
        section('publications', { entries: [item({ title: 'Falls in older adults', organization: 'Nursing Times', start_date: '2025-03' })] }),
        section('custom-a1', { kind: 'custom', title: 'Hobbies', entries: [item({ title: 'Marathons' })] }),
      ],
    }

    const doc = buildDocument(data, 'resume', {}, CATALOG)

    expect(doc.sections.map((s) => s.heading)).toEqual([
      'Profile', 'Clinical Experience', 'Education', 'Skills', 'Languages', 'Publications', 'Hobbies',
      'Projects', // has content but wasn't listed: appended, never dropped
    ])
    const clinical = doc.sections[1].entries[0]
    expect(clinical).toMatchObject({ title: "Student Nurse, St Mary's", date: 'Jan 2024 – Present', bullets: ['Monitored vitals'] })
    expect(doc.sections[4].text).toBe('Spanish (Fluent), Welsh')
    expect(doc.sections[5].entries[0].date).toBe('Mar 2025') // single date
  })

  it('leaves out empty sections', () => {
    const data = { ...base, sections: [section('summary'), section('publications'), section('experience')] }

    // Empty Publications and Experience don't print; unlisted core sections with content follow.
    expect(buildDocument(data, 'resume', {}, CATALOG).sections.map((s) => s.key)).toEqual(['summary', 'skills', 'projects', 'education'])
  })

  it('uses the old fixed order for resumes saved before sections existed', () => {
    expect(orderedSections(base).map((s) => s.id)).toEqual([
      'summary', 'skills', 'experience', 'projects', 'education', 'certifications', 'achievements',
    ])
  })
})
