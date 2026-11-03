import { describe, expect, it } from 'vitest'

import { emptyItem, sectionItemForm, type ResumeFormValues } from '@/features/resumes/form-schema'
import type { SectionItem } from '@/features/resumes/types'

import { withBullet, withSectionEntry } from './apply'

const publication: SectionItem = {
  title: 'Drought shifts the wheat root microbiome', organization: 'Journal of Plant Science', location: null,
  start_date: '2023-03', end_date: null, is_current: false, description: 'Novak T., Hill S.', bullets: [],
  link: 'doi.org/10.1234/jps.2023.44', proof_id: 'p1',
}

function data(): ResumeFormValues['data'] {
  const job = { ...emptyItem.experience(), title: 'Staff Nurse', company: "St Mary's", bullets: [{ value: 'Assessed patients' }, { value: '' }] }
  const placement = { ...emptyItem.sectionItem(), title: 'Student Nurse', bullets: [] }
  return {
    experience: [job],
    sections: [{ id: 'clinical_experience', kind: 'clinical_experience', title: '', entries: [placement] }],
  } as unknown as ResumeFormValues['data']
}

describe('withSectionEntry', () => {
  it('adds a Publications section when the resume has none', () => {
    const sections = withSectionEntry(data().sections, 'publications', publication)
    expect(sections?.map((s) => s.id)).toEqual(['clinical_experience', 'publications'])
    expect(sections?.[1].entries[0]).toEqual(sectionItemForm(publication))
    expect(sections?.[1].entries[0].link).toBe('doi.org/10.1234/jps.2023.44')
  })

  it('appends to the existing section of that kind', () => {
    const once = withSectionEntry(data().sections, 'publications', publication)!
    const twice = withSectionEntry(once, 'publications', { ...publication, title: 'Second paper' })
    expect(twice?.find((s) => s.kind === 'publications')?.entries.map((e) => e.title)).toEqual([publication.title, 'Second paper'])
  })
})

describe('withBullet', () => {
  it('adds the bullet to the job, dropping blank rows', () => {
    const result = withBullet(data(), { section_id: 'experience', item_index: 0, item_title: 'Staff Nurse', label: '' }, 'Produced a care plan')
    expect(result).toEqual({ path: 'data.experience.0.bullets', bullets: [{ value: 'Assessed patients' }, { value: 'Produced a care plan' }] })
  })

  it('adds the bullet to an entry in a section like Clinical Experience', () => {
    const result = withBullet(data(), { section_id: 'clinical_experience', item_index: 0, item_title: 'Student Nurse', label: '' }, 'Produced a care plan')
    expect(result?.path).toBe('data.sections.0.entries.0.bullets')
    expect(result?.bullets).toEqual([{ value: 'Produced a care plan' }])
  })

  it('refuses when the entry moved or was renamed since', () => {
    expect(withBullet(data(), { section_id: 'experience', item_index: 0, item_title: 'Healthcare Assistant', label: '' }, 'x')).toBeNull()
    expect(withBullet(data(), { section_id: 'volunteer', item_index: 0, item_title: 'Student Nurse', label: '' }, 'x')).toBeNull()
  })
})
