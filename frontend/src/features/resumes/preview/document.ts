// Mirror of backend/app/services/export/document.py so the live preview shows exactly
// what the PDF/DOCX export will contain. Keep the two in sync.
import type { ProofLinks } from '@/features/suggestions/types'

import type { SectionCatalog } from '../sections/api'
import type { CoreKind, ResumeData, ResumeType, SectionConfig, SectionItem, SectionKind } from '../types'
import { isCoreKind } from '../types'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DASH = '–'

// Used until the section catalog has loaded (and for core kinds it never differs).
const FALLBACK_HEADINGS: Partial<Record<SectionKind, string>> = {
  summary: 'Summary',
  skills: 'Skills',
  experience: 'Experience',
  projects: 'Projects',
  education: 'Education',
  certifications: 'Licenses & Certifications',
  achievements: 'Achievements',
}

// Resumes saved before sections were configurable (the backend fills these in too).
const DEFAULT_ORDER: CoreKind[] = ['summary', 'skills', 'experience', 'projects', 'education', 'certifications', 'achievements']

export interface Entry {
  title: string
  date: string
  subtitle: string
  link: string
  description: string
  bullets: string[]
  tools: string[]
}

export interface Section {
  /** The section's id. */
  key: string
  heading: string
  text: string
  entries: Entry[]
  items: string[]
  extra: string[]
}

export interface ResumeDocument {
  name: string
  headline: string
  contact: string[]
  sections: Section[]
}

/** YYYY-MM -> "Mar 2024". Invalid half-typed values are shown as typed. */
export function formatYearMonth(value: string | null): string {
  if (!value) return ''
  const match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(value)
  return match ? `${MONTHS[Number(match[2]) - 1]} ${match[1]}` : value
}

export function formatDateRange(start: string | null, end: string | null, isCurrent: boolean) {
  const begin = formatYearMonth(start)
  const finish = isCurrent ? 'Present' : formatYearMonth(end)
  if (begin && finish) return `${begin} ${DASH} ${finish}`
  return begin || finish
}

const join = (parts: (string | null)[], sep = ', ') => parts.filter(Boolean).join(sep)

const entry = (fields: Partial<Entry> & { title: string }): Entry => ({
  date: '', subtitle: '', link: '', description: '', bullets: [], tools: [], ...fields,
})

const hasContent = (e: Entry) =>
  Boolean(e.title || e.date || e.subtitle || e.link || e.description || e.bullets.length || e.tools.length)

/** "Verified skills: Git (github.com/ada/tracker), ..." — skills backed by verified proofs. */
export function verifiedSkillsLine(data: ResumeData, proofs: ProofLinks): string {
  const cited = data.skills.flatMap((skill) => {
    const proof = skill.proof_id ? proofs[skill.proof_id] : undefined
    if (!skill.name || !proof?.verified) return []
    return [proof.display_url ? `${skill.name} (${proof.display_url})` : skill.name]
  })
  return cited.length ? `Verified skills: ${cited.join(', ')}` : ''
}

/** Sections in the user's order; core sections with content are never dropped. */
export function orderedSections(data: ResumeData): SectionConfig[] {
  const listed: SectionConfig[] = data.sections?.length
    ? data.sections
    : DEFAULT_ORDER.map((kind) => ({ id: kind, kind, title: null, entries: [] }))
  const kinds = new Set(listed.map((s) => s.kind))
  const hasContent: Record<CoreKind, boolean> = {
    summary: Boolean(data.summary.trim()), experience: data.experience.length > 0,
    education: data.education.length > 0, skills: data.skills.length > 0, projects: data.projects.length > 0,
    certifications: data.certifications.length > 0, achievements: data.achievements.length > 0,
  }
  const missing = DEFAULT_ORDER.filter((kind) => !kinds.has(kind) && hasContent[kind])
  return [...listed, ...missing.map((kind): SectionConfig => ({ id: kind, kind, title: null, entries: [] }))]
}

const itemHasContent = (i: SectionItem) => Boolean(i.title || i.organization || i.description || i.bullets.length || i.link)

export function buildDocument(
  data: ResumeData,
  type: ResumeType,
  proofs: ProofLinks = {},
  catalog: SectionCatalog = {},
): ResumeDocument {
  void type // order comes from data.sections; the type only matters for new resumes
  const proofUrl = (id: string | null) => (id ? proofs[id]?.display_url ?? '' : '')
  const p = data.personal_info
  const contact = [
    ...[p.email, p.phone, p.location].filter((c): c is string => Boolean(c)),
    ...(p.profile_links ?? []).map((link) => link.url),
  ]

  const section = (key: string, fields: Partial<Section> = {}): Section => ({
    key, heading: '', text: '', entries: [], items: [], extra: [], ...fields,
  })

  const byKey: Record<CoreKind, Section> = {
    summary: section('summary', { text: data.summary }),
    skills: section('skills', {
      text: data.skills.map((s) => s.name).filter(Boolean).join(', '),
      extra: data.show_verified_skills && verifiedSkillsLine(data, proofs) ? [verifiedSkillsLine(data, proofs)] : [],
    }),
    experience: section('experience', {
      entries: data.experience.map((e) =>
        entry({
          title: join([e.title, e.company]),
          date: formatDateRange(e.start_date, e.end_date, e.is_current),
          subtitle: e.location ?? '',
          bullets: e.bullets,
          tools: e.tools_and_skills,
        }),
      ),
    }),
    projects: section('projects', {
      entries: data.projects.map((pr) =>
        entry({
          title: pr.name, link: pr.link || proofUrl(pr.proof_id), description: pr.description,
          bullets: pr.bullets, tools: pr.tools_and_skills,
        }),
      ),
    }),
    education: section('education', {
      entries: data.education.map((e) =>
        entry({
          title: e.institution,
          date: formatDateRange(e.start_date, e.end_date, e.is_current),
          subtitle: join([join([e.degree, e.field_of_study], ' in '), e.grade]),
          bullets: e.bullets,
        }),
      ),
    }),
    certifications: section('certifications', {
      entries: data.certifications.map((c) =>
        entry({
          title: c.name, date: formatYearMonth(c.issue_date), subtitle: c.issuer ?? '',
          link: c.credential_url || proofUrl(c.proof_id),
          description: c.credential_id ? `Credential ID: ${c.credential_id}` : '',
        }),
      ),
    }),
    achievements: section('achievements', { items: data.achievements.filter(Boolean) }),
  }

  const generic = (config: SectionConfig): Section => {
    const spec = catalog[config.kind]
    const items = config.entries.filter(itemHasContent)
    if (spec?.layout === 'inline') {
      const text = items
        .filter((i) => i.title)
        .map((i) => (i.organization ? `${i.title} (${i.organization})` : i.title))
        .join(', ')
      return section(config.id, { text })
    }
    const single = spec?.fields?.dates === 'single'
    return section(config.id, {
      entries: items.map((i) =>
        entry({
          title: join([i.title, i.organization]),
          date: single ? formatYearMonth(i.start_date || i.end_date) : formatDateRange(i.start_date, i.end_date, i.is_current),
          subtitle: i.location ?? '',
          link: i.link || proofUrl(i.proof_id),
          description: i.description,
          bullets: i.bullets,
        }),
      ),
    })
  }

  const sections = orderedSections(data)
    .map((config) => {
      const built = isCoreKind(config.kind) ? byKey[config.kind] : generic(config)
      const heading = config.title || catalog[config.kind]?.heading || FALLBACK_HEADINGS[config.kind] || 'Section'
      return { ...built, heading, entries: built.entries.filter(hasContent) }
    })
    .filter((s) => s.text || s.entries.length || s.items.length)

  return { name: p.full_name, headline: p.headline, contact, sections }
}
