import type { ResumeFormValues } from '../form-schema'

type Data = ResumeFormValues['data']
/** 'personal-info', a core section, or any section id from `data.sections`. */
export type SectionId = string

export interface Completion {
  state: 'complete' | 'partial' | 'empty'
  /** Short status for the section header, e.g. "2 positions" or "Add an email". */
  detail: string
  /** Optional sections don't count against overall completeness. */
  optional: boolean
}

const has = (value: string | undefined) => Boolean(value && value.trim())
const plural = (n: number, word: string, many = `${word}s`) => `${n} ${n === 1 ? word : many}`

/** What "filled in" means for each section. Kept deliberately simple and explainable. */
export function sectionCompletion(id: SectionId, data: Data): Completion {
  const section = data.sections.find((s) => s.id === id)
  if (section && section.kind !== id) return entriesCompletion(section)
  switch (id) {
    case 'personal-info': {
      const p = data.personal_info
      const missing = [!has(p.full_name) && 'name', !has(p.email) && 'email', !has(p.phone) && !has(p.location) && 'phone or location'].filter(Boolean)
      if (missing.length === 0) return { state: 'complete', detail: 'Complete', optional: false }
      const any = [p.full_name, p.email, p.phone, p.location, p.headline].some(has)
      return { state: any ? 'partial' : 'empty', detail: `Add your ${missing.join(', ')}`, optional: false }
    }
    case 'summary': {
      const length = data.summary.trim().length
      if (length >= 40) return { state: 'complete', detail: 'Complete', optional: false }
      return { state: length ? 'partial' : 'empty', detail: length ? 'A bit more detail' : 'Not started', optional: false }
    }
    case 'experience': {
      const done = data.experience.filter((e) => has(e.title) && has(e.company) && e.bullets.some((b) => has(b.value))).length
      if (done > 0 && done === data.experience.length) return { state: 'complete', detail: plural(done, 'position'), optional: false }
      if (data.experience.length === 0) return { state: 'empty', detail: 'Not started', optional: false }
      return { state: 'partial', detail: 'Add a title, company and a highlight', optional: false }
    }
    case 'education': {
      const done = data.education.filter((e) => has(e.institution) && has(e.degree)).length
      if (done > 0 && done === data.education.length) return { state: 'complete', detail: plural(done, 'entry', 'entries'), optional: false }
      if (data.education.length === 0) return { state: 'empty', detail: 'Not started', optional: false }
      return { state: 'partial', detail: 'Add an institution and degree', optional: false }
    }
    case 'projects': {
      const done = data.projects.filter((p) => has(p.name) && (has(p.description) || p.bullets.some((b) => has(b.value)))).length
      if (done > 0 && done === data.projects.length) return { state: 'complete', detail: plural(done, 'project'), optional: true }
      if (data.projects.length === 0) return { state: 'empty', detail: 'Optional', optional: true }
      return { state: 'partial', detail: 'Add a name and what you built', optional: true }
    }
    case 'skills': {
      const named = data.skills.filter((s) => has(s.name)).length
      if (named >= 3) return { state: 'complete', detail: plural(named, 'skill'), optional: false }
      return { state: named ? 'partial' : 'empty', detail: named ? `${named} of 3+ skills` : 'Not started', optional: false }
    }
    case 'certifications': {
      const named = data.certifications.filter((c) => has(c.name)).length
      return named ? { state: 'complete', detail: plural(named, 'certification'), optional: true } : { state: 'empty', detail: 'Optional', optional: true }
    }
    case 'achievements': {
      const named = data.achievements.filter((a) => has(a.value)).length
      return named ? { state: 'complete', detail: plural(named, 'achievement'), optional: true } : { state: 'empty', detail: 'Optional', optional: true }
    }
  }

  if (section) return entriesCompletion(section)
  return { state: 'empty', detail: 'Not started', optional: true }
}

/** Non-core sections (placements, publications, languages...): done once an entry has a title. */
function entriesCompletion(section: Data['sections'][number]): Completion {
  const named = section.entries.filter((e) => has(e.title)).length
  if (named > 0 && named === section.entries.length) {
    return { state: 'complete', detail: plural(named, 'entry', 'entries'), optional: false }
  }
  if (section.entries.length === 0) return { state: 'empty', detail: 'Not started', optional: false }
  return { state: 'partial', detail: 'Give each entry a title', optional: false }
}

/** Sections that count towards "N of M sections complete": personal info plus every section
 * the user chose to show (they're on the resume, so they should be filled in). */
export function trackedSections(data: Data): SectionId[] {
  return ['personal-info', ...data.sections.map((s) => s.id)]
}
