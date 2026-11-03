import { describe, expect, it } from 'vitest'

import { emptyItem, LIMITS, resumeFormSchema, toFormValues, toResumeData } from './form-schema'
import type { Resume } from './types'

const resume: Resume = {
  id: 'r1',
  title: 'Main',
  type: 'resume',
  template: 'classic',
  target_role: null,
  experience_level: null,
  ats_score: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  data: {
    personal_info: { full_name: 'Ada', headline: '', email: 'ada@example.com', phone: null, location: null, profile_links: [] },
    summary: 'Engineer.',
    experience: [
      { company: 'Acme', title: 'Dev', location: null, start_date: '2024-01', end_date: null, is_current: true, bullets: ['Built the API'], tools_and_skills: ['Python', 'SQL'] },
    ],
    education: [],
    projects: [],
    skills: [{ name: 'Git', skill_id: null, proof_id: null }],
    certifications: [],
    achievements: [],
    show_verified_skills: false,
    sections: [],
  },
}

describe('resume form schema', () => {
  it('round-trips API data through the form shape', () => {
    const values = toFormValues(resume)

    expect(values.data.experience[0].bullets).toEqual([{ value: 'Built the API' }])
    expect(values.data.experience[0].tools_and_skills).toBe('Python, SQL')
    expect(toResumeData(values)).toEqual(resume.data)
  })

  it('enforces the same caps as the server', () => {
    const values = toFormValues(resume)
    values.data.experience[0].bullets = Array.from({ length: LIMITS.bullets + 1 }, () => ({ value: 'x' }))
    values.data.skills = Array.from({ length: LIMITS.skills + 1 }, () => emptyItem.skills())

    const result = resumeFormSchema.safeParse(values)

    expect(result.success).toBe(false)
    const messages = result.error?.issues.map((i) => i.message) ?? []
    expect(messages).toContain('You can add up to 15 bullets')
    expect(messages).toContain('You can add up to 100 skills')
  })

  it('catches contradictory dates', () => {
    const values = toFormValues(resume)
    values.data.experience[0] = { ...values.data.experience[0], is_current: false, start_date: '2024-05', end_date: '2023-01' }

    const result = resumeFormSchema.safeParse(values)

    expect(result.error?.issues.map((i) => i.message)).toContain('End date is before start date')
  })

  it('round-trips sections, their order, renames and entries', () => {
    const withSections: Resume = {
      ...resume,
      data: {
        ...resume.data,
        sections: [
          { id: 'skills', kind: 'skills', title: 'Key Skills', entries: [] },
          {
            id: 'volunteer',
            kind: 'volunteer',
            title: null,
            entries: [
              { title: 'Ward Volunteer', organization: 'Red Cross', location: null, start_date: '2023-01', end_date: null, is_current: true, description: '', bullets: ['Greeted 40 visitors a day'], link: null, proof_id: null },
            ],
          },
          { id: 'summary', kind: 'summary', title: null, entries: [] },
        ],
      },
    }

    const values = toFormValues(withSections)

    expect(values.data.sections[1].entries[0].bullets).toEqual([{ value: 'Greeted 40 visitors a day' }])
    expect(toResumeData(values)).toEqual(withSections.data)
  })

  it('requires custom sections to have a name', () => {
    const values = toFormValues(resume)
    values.data.sections = [emptyItem.section('custom')]

    const result = resumeFormSchema.safeParse(values)

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]).toMatchObject({ path: ['data', 'sections', 0, 'title'], message: 'Give this section a name' })
    expect(emptyItem.section('custom').id).toMatch(/^custom-[a-z0-9]+$/)
    expect(emptyItem.section('publications').id).toBe('publications')
  })
})
