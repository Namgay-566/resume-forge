import { emptyItem, LIMITS, sectionItemForm, type ResumeFormValues } from '@/features/resumes/form-schema'
import type { SectionItem, SectionKind } from '@/features/resumes/types'

import type { BulletTarget } from './types'

type FormData = ResumeFormValues['data']

/** Sections with the entry added to the first section of that kind (added if missing). */
export function withSectionEntry(sections: FormData['sections'], kind: SectionKind, entry: SectionItem): FormData['sections'] | null {
  const index = sections.findIndex((s) => s.kind === kind)
  const target = index === -1 ? emptyItem.section(kind) : sections[index]
  if (target.entries.length >= LIMITS.entries) return null
  const updated = { ...target, entries: [...target.entries, sectionItemForm(entry)] }
  if (index === -1) return sections.length >= LIMITS.sections ? null : [...sections, updated]
  return sections.map((s, i) => (i === index ? updated : s))
}

export type BulletResult =
  | { path: `data.experience.${number}.bullets`; bullets: FormData['experience'][number]['bullets'] }
  | { path: `data.sections.${number}.entries.${number}.bullets`; bullets: FormData['experience'][number]['bullets'] }

/** Where the bullet goes and the entry's new bullets; null if the entry moved or changed
 * since the suggestion was made (its title no longer matches) or is full. */
export function withBullet(data: FormData, target: BulletTarget, bullet: string): BulletResult | null {
  const append = (bullets: { value: string }[]) =>
    bullets.length >= LIMITS.bullets ? null : [...bullets.filter((b) => b.value.trim()), { value: bullet }]
  if (target.section_id === 'experience') {
    const job = data.experience[target.item_index]
    if (!job || job.title.trim() !== target.item_title.trim()) return null
    const bullets = append(job.bullets)
    return bullets && { path: `data.experience.${target.item_index}.bullets`, bullets }
  }
  const sectionIndex = data.sections.findIndex((s) => s.id === target.section_id)
  const entry = data.sections[sectionIndex]?.entries[target.item_index]
  if (!entry || entry.title.trim() !== target.item_title.trim()) return null
  const bullets = append(entry.bullets)
  return bullets && { path: `data.sections.${sectionIndex}.entries.${target.item_index}.bullets`, bullets }
}
