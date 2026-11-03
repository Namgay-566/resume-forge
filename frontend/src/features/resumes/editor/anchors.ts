import type { Location, SectionKey } from '@/features/ats/types'

// Editor card ids for ATS locations. Anything else (a section id) is its own card id.
const SECTION_IDS: Partial<Record<SectionKey, string>> = {
  personal_info: 'personal-info',
  summary: 'summary',
  experience: 'experience',
  education: 'education',
  projects: 'projects',
  skills: 'skills',
  certifications: 'certifications',
  achievements: 'achievements',
}

/** DOM ids the ATS fix list scrolls to. SectionCard/ItemCard render these. */
export const sectionAnchor = (cardId: string) => `section-${cardId}`
export const itemAnchor = (cardId: string, index: number) => `section-${cardId}-item-${index}`

/** Collapsed sections and items open when this names their anchor id. */
export const OPEN_EVENT = 'rf:open-anchor'

export function scrollToLocation(location: Location) {
  const cardId = SECTION_IDS[location.section as SectionKey] ?? location.section
  // Expand the section (and the item) first; collapsed content isn't in the layout.
  const ids = [sectionAnchor(cardId)]
  if (location.item_index !== null) ids.push(itemAnchor(cardId, location.item_index))
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: ids }))
  window.setTimeout(() => reveal(cardId, location), 230) // after the expand animation
}

function reveal(cardId: string, location: Location) {
  const target =
    (location.item_index !== null && document.getElementById(itemAnchor(cardId, location.item_index))) ||
    document.getElementById(sectionAnchor(cardId))
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target.querySelector<HTMLElement>('input, textarea')?.focus({ preventScroll: true })
  target.classList.add('ats-highlight')
  window.setTimeout(() => target.classList.remove('ats-highlight'), 1800)
}
