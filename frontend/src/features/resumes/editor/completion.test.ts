import { describe, expect, it } from 'vitest'

import { emptyItem, toFormValues } from '../form-schema'
import type { Resume } from '../types'
import { sectionCompletion, trackedSections } from './completion'

const blank = toFormValues({
  id: 'r', title: 'T', type: 'resume', template: 'classic', target_role: null, experience_level: null, ats_score: null, created_at: '', updated_at: '',
  data: {
    personal_info: { full_name: '', headline: '', email: null, phone: null, location: null, profile_links: [] },
    summary: '', experience: [], education: [], projects: [], skills: [], certifications: [], achievements: [], show_verified_skills: false,
    sections: [],
  },
} as Resume).data

describe('sectionCompletion', () => {
  it('says what is missing, then checks the section off', () => {
    expect(sectionCompletion('personal-info', blank)).toMatchObject({ state: 'empty' })
    const partial = { ...blank, personal_info: { ...blank.personal_info, full_name: 'Ada' } }
    expect(sectionCompletion('personal-info', partial)).toEqual({ state: 'partial', detail: 'Add your email, phone or location', optional: false })
    const full = { ...partial, personal_info: { ...partial.personal_info, email: 'a@x.dev', location: 'Berlin' } }
    expect(sectionCompletion('personal-info', full).state).toBe('complete')
  })

  it('needs every experience entry to have a title, company and a highlight', () => {
    const job = { ...emptyItem.experience(), title: 'Dev', company: 'Acme' }
    expect(sectionCompletion('experience', { ...blank, experience: [job] }).state).toBe('partial')
    const withBullet = { ...job, bullets: [{ value: 'Built the API' }] }
    expect(sectionCompletion('experience', { ...blank, experience: [withBullet] })).toMatchObject({ state: 'complete', detail: '1 position' })
  })

  it('treats projects, certifications and achievements as optional', () => {
    expect(sectionCompletion('certifications', blank)).toEqual({ state: 'empty', detail: 'Optional', optional: true })
    const skills = ['Git', 'SQL'].map((name) => ({ ...emptyItem.skills(), name }))
    expect(sectionCompletion('skills', { ...blank, skills }).detail).toBe('2 of 3+ skills')
  })

  it('tracks every section on the resume, including new kinds', () => {
    const volunteer = { ...emptyItem.section('volunteer'), entries: [{ ...emptyItem.sectionItem(), title: 'Ward Volunteer' }] }
    const data = { ...blank, sections: [emptyItem.section('summary'), volunteer, emptyItem.section('publications')] }

    expect(trackedSections(data)).toEqual(['personal-info', 'summary', 'volunteer', 'publications'])
    expect(sectionCompletion('volunteer', data)).toMatchObject({ state: 'complete', detail: '1 entry' })
    expect(sectionCompletion('publications', data)).toMatchObject({ state: 'empty', optional: false })
  })
})

