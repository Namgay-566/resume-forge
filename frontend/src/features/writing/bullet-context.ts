import type { ResumeFormValues } from '@/features/resumes/form-schema'
import type { SectionKind } from '@/features/resumes/types'

import type { ImproveBulletInput } from './api'

type FormData = ResumeFormValues['data']

export interface BulletContext extends Omit<ImproveBulletInput, 'text'> {
  /** Form path of the bullet's text. */
  path: string
}

const at = (...parts: string[]) => parts.map((p) => p.trim()).filter(Boolean).join(' at ')
const split = (list: string) => list.split(',').map((t) => t.trim()).filter(Boolean)

/**
 * What the AI needs to know about the bullet at `index` of the row list `name`: which
 * section it's in (so a volunteering bullet reads like volunteering), and the entry it
 * belongs to. Null for row lists that aren't bullets.
 */
export function bulletContext(data: FormData, name: string, index: number): BulletContext | null {
  const path = `${name}.${index}.value`
  if (name === 'data.achievements') {
    return { path, section: 'achievements', section_title: null, position: '', tools_and_skills: [] }
  }
  const core = /^data\.(experience|education|projects)\.(\d+)\.bullets$/.exec(name)
  if (core) {
    const i = Number(core[2])
    if (core[1] === 'experience') {
      const job = data.experience[i]
      if (!job) return null
      return { path, section: 'experience', section_title: title(data, 'experience'), position: at(job.title, job.company), tools_and_skills: split(job.tools_and_skills) }
    }
    if (core[1] === 'education') {
      const course = data.education[i]
      if (!course) return null
      const degree = [course.degree, course.field_of_study].map((p) => p.trim()).filter(Boolean).join(', ')
      return { path, section: 'education', section_title: title(data, 'education'), position: at(degree, course.institution), tools_and_skills: [] }
    }
    const project = data.projects[i]
    if (!project) return null
    return { path, section: 'projects', section_title: title(data, 'projects'), position: project.name.trim(), tools_and_skills: split(project.tools_and_skills) }
  }
  const generic = /^data\.sections\.(\d+)\.entries\.(\d+)\.bullets$/.exec(name)
  if (generic) {
    const section = data.sections[Number(generic[1])]
    const entry = section?.entries[Number(generic[2])]
    if (!section || !entry) return null
    return { path, section: section.kind, section_title: section.title.trim() || null, position: at(entry.title, entry.organization), tools_and_skills: [] }
  }
  return null
}

/** A renamed core section's heading (e.g. "Work History"), or null for the standard one. */
function title(data: FormData, kind: SectionKind): string | null {
  return data.sections.find((s) => s.kind === kind)?.title.trim() || null
}
