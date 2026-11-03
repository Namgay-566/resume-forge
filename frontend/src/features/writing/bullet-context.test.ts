import { describe, expect, it } from 'vitest'

import { toFormValues } from '@/features/resumes/form-schema'
import type { Resume } from '@/features/resumes/types'

import { bulletContext } from './bullet-context'

const entry = (title: string, organization: string, bullets: string[]) => ({
  title, organization, location: null, start_date: null, end_date: null, is_current: false,
  description: '', bullets, link: null, proof_id: null,
})

const resume = {
  id: 'r', title: 'CV', type: 'cv', template: 'classic', target_role: null, experience_level: null,
  ats_score: null, created_at: '', updated_at: '',
  data: {
    personal_info: { full_name: 'Priya', headline: '', email: null, phone: null, location: null, profile_links: [] },
    summary: '',
    experience: [{ company: "St Mary's Hospital", title: 'Staff Nurse', location: null, start_date: null, end_date: null, is_current: false, bullets: ['Cared for patients'], tools_and_skills: ['Epic', 'IV pumps'] }],
    education: [{ institution: "King's College London", degree: 'BSc', field_of_study: 'Adult Nursing', grade: null, start_date: null, end_date: null, is_current: false, bullets: ['Dissertation on falls'] }],
    projects: [],
    skills: [],
    certifications: [],
    achievements: ['Nurse of the month'],
    show_verified_skills: false,
    sections: [
      { id: 'experience', kind: 'experience', title: 'Work History', entries: [] },
      { id: 'volunteer', kind: 'volunteer', title: null, entries: [entry('First Aid Volunteer', 'St John Ambulance', ['Helped at events'])] },
      { id: 'custom-fieldwork', kind: 'custom', title: 'Fieldwork', entries: [entry('Rothamsted', '', ['Sampled soil'])] },
    ],
  },
} satisfies Resume

const data = toFormValues(resume).data

describe('bulletContext', () => {
  it('describes a job bullet with its entry, tools and renamed heading', () => {
    expect(bulletContext(data, 'data.experience.0.bullets', 0)).toEqual({
      path: 'data.experience.0.bullets.0.value',
      section: 'experience',
      section_title: 'Work History',
      position: "Staff Nurse at St Mary's Hospital",
      tools_and_skills: ['Epic', 'IV pumps'],
    })
  })

  it('works for education and achievements', () => {
    expect(bulletContext(data, 'data.education.0.bullets', 0)).toMatchObject({
      section: 'education', section_title: null, position: "BSc, Adult Nursing at King's College London",
    })
    expect(bulletContext(data, 'data.achievements', 0)).toMatchObject({ path: 'data.achievements.0.value', section: 'achievements' })
  })

  it('works for flexible sections, including custom ones by name', () => {
    expect(bulletContext(data, 'data.sections.1.entries.0.bullets', 0)).toMatchObject({
      path: 'data.sections.1.entries.0.bullets.0.value', section: 'volunteer', section_title: null,
      position: 'First Aid Volunteer at St John Ambulance',
    })
    expect(bulletContext(data, 'data.sections.2.entries.0.bullets', 0)).toMatchObject({
      section: 'custom', section_title: 'Fieldwork', position: 'Rothamsted',
    })
  })

  it('returns null for entries that no longer exist', () => {
    expect(bulletContext(data, 'data.experience.5.bullets', 0)).toBeNull()
    expect(bulletContext(data, 'data.sections.9.entries.0.bullets', 0)).toBeNull()
    expect(bulletContext(data, 'data.skills', 0)).toBeNull()
  })
})
