import { z } from 'zod'

import { SECTION_KINDS, type Resume, type ResumeData, type ResumeTemplate, type ResumeType, type ProjectItem, type ResumeUpdate, type SectionConfig, type SectionItem, type SectionKind } from './types'

// Mirrors backend/app/schemas/resume_data.py so errors show inline before the server sees them.
// Form values use '' for "empty" and {value} rows (RHF field arrays need objects);
// toPayload() converts back to the API shape.

const text = (max = 200) => z.string().max(max, `Keep this under ${max} characters`)
const yearMonth = z.union([
  z.literal(''),
  z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/, 'Use YYYY-MM, e.g. 2024-03'),
])
const optionalEmail = z.union([z.literal(''), z.email('Enter a valid email address')])
// Caps mirror backend MAX_* limits in resume_data.py (they bound every AI prompt too).
export const LIMITS = { bullets: 15, tools: 30, entries: 30, education: 15, skills: 100, certifications: 50, sections: 30, profileLinks: 8 } as const
const list = <T extends z.ZodType>(item: T, max: number, what: string) =>
  z.array(item).max(max, `You can add up to ${max} ${what}`)
const listText = z
  .string()
  .max(1000, 'Too long')
  .refine((v) => v.split(',').filter((t) => t.trim()).length <= LIMITS.tools, `List up to ${LIMITS.tools} tools and skills`)
const bullets = () => list(z.object({ value: text(500) }), LIMITS.bullets, 'bullets')
const row = z.object({ value: text(500) })
const idOrNull = z.string().nullable()

const dateRange = {
  start_date: yearMonth,
  end_date: yearMonth,
  is_current: z.boolean(),
}

function checkDates(item: { start_date: string; end_date: string; is_current: boolean }, ctx: z.RefinementCtx) {
  if (item.is_current && item.end_date) {
    ctx.addIssue({ code: 'custom', path: ['end_date'], message: 'Leave empty for a current role' })
  }
  // Zero-padded YYYY-MM strings compare correctly as text.
  if (item.start_date && item.end_date && item.end_date < item.start_date) {
    ctx.addIssue({ code: 'custom', path: ['end_date'], message: 'End date is before start date' })
  }
}

const experienceItem = z
  .object({
    company: text(),
    title: text(),
    location: text(),
    ...dateRange,
    bullets: bullets(),
    tools_and_skills: listText,
  })
  .superRefine(checkDates)

const educationItem = z
  .object({
    institution: text(),
    degree: text(),
    field_of_study: text(),
    grade: text(40),
    ...dateRange,
    bullets: bullets(),
  })
  .superRefine(checkDates)

const projectItem = z.object({
  name: text(),
  description: text(1000),
  bullets: bullets(),
  tools_and_skills: listText,
  link: text(),
  proof_id: idOrNull,
})

const skillItem = z.object({ name: text(), skill_id: idOrNull, proof_id: idOrNull })

const certificationItem = z.object({
  name: text(),
  issuer: text(),
  issue_date: yearMonth,
  credential_id: text(100),
  credential_url: text(),
  proof_id: idOrNull,
})

const sectionItem = z
  .object({
    title: text(),
    organization: text(),
    location: text(),
    ...dateRange,
    description: text(1000),
    bullets: bullets(),
    link: text(),
    proof_id: idOrNull,
  })
  .superRefine(checkDates)

const sectionConfig = z
  .object({
    id: z.string(),
    kind: z.enum(SECTION_KINDS),
    title: text(),
    entries: list(sectionItem, LIMITS.entries, 'entries'),
  })
  .superRefine((section, ctx) => {
    if (section.kind === 'custom' && !section.title.trim()) {
      ctx.addIssue({ code: 'custom', path: ['title'], message: 'Give this section a name' })
    }
  })

// A link needs both a name ("ORCID") and an address; fully blank rows are dropped on save.
const profileLink = z
  .object({ label: text(40), url: text(200) })
  .superRefine((link, ctx) => {
    if (link.url.trim() && !link.label.trim()) {
      ctx.addIssue({ code: 'custom', path: ['label'], message: 'Name this link, e.g. LinkedIn' })
    }
    if (link.label.trim() && !link.url.trim()) {
      ctx.addIssue({ code: 'custom', path: ['url'], message: 'Add the address' })
    }
  })

export const resumeFormSchema = z.object({
  title: z.string().trim().min(1, 'Give this resume a name').max(200),
  type: z.enum(['resume', 'cv']),
  template: z.enum(['classic', 'modern_minimal', 'compact', 'conservative', 'professional', 'academic']),
  target_role_id: z.string().nullable(),
  experience_level: z.enum(['student', 'entry', 'mid', 'senior', 'career_changer']).nullable(),
  data: z.object({
    personal_info: z.object({
      full_name: text(),
      headline: text(),
      email: optionalEmail,
      phone: text(40),
      location: text(),
      profile_links: list(profileLink, LIMITS.profileLinks, 'profile links'),
    }),
    summary: text(2000),
    experience: list(experienceItem, LIMITS.entries, 'jobs'),
    education: list(educationItem, LIMITS.education, 'education entries'),
    projects: list(projectItem, LIMITS.entries, 'projects'),
    skills: list(skillItem, LIMITS.skills, 'skills'),
    certifications: list(certificationItem, LIMITS.certifications, 'certifications'),
    achievements: list(row, LIMITS.entries, 'achievements'),
    show_verified_skills: z.boolean(),
    sections: list(sectionConfig, LIMITS.sections, 'sections'),
  }),
})

export type ResumeFormValues = z.infer<typeof resumeFormSchema>
type FormData = ResumeFormValues['data']

// --- empty items for "Add" buttons -------------------------------------------

export const emptyItem = {
  experience: (): FormData['experience'][number] => ({
    company: '', title: '', location: '', start_date: '', end_date: '', is_current: false,
    bullets: [{ value: '' }], tools_and_skills: '',
  }),
  education: (): FormData['education'][number] => ({
    institution: '', degree: '', field_of_study: '', grade: '', start_date: '', end_date: '',
    is_current: false, bullets: [],
  }),
  projects: (): FormData['projects'][number] => ({
    name: '', description: '', bullets: [{ value: '' }], tools_and_skills: '', link: '', proof_id: null,
  }),
  skills: (): FormData['skills'][number] => ({ name: '', skill_id: null, proof_id: null }),
  certifications: (): FormData['certifications'][number] => ({
    name: '', issuer: '', issue_date: '', credential_id: '', credential_url: '', proof_id: null,
  }),
  row: () => ({ value: '' }),
  profileLink: (label = '') => ({ label, url: '' }),
  sectionItem: (): FormData['sections'][number]['entries'][number] => ({
    title: '', organization: '', location: '', start_date: '', end_date: '', is_current: false,
    description: '', bullets: [], link: '', proof_id: null,
  }),
  /** A new section. Custom ones get a random id so there can be several. */
  section: (kind: SectionKind, title = ''): FormData['sections'][number] => ({
    id: kind === 'custom' ? `custom-${Math.random().toString(36).slice(2, 10)}` : kind,
    kind,
    title,
    entries: [],
  }),
}

// --- API <-> form --------------------------------------------------------------

const str = (value: string | null | undefined) => value ?? ''
const rows = (values: string[]) => values.map((value) => ({ value }))
const joinList = (values: string[]) => values.join(', ')

export function projectForm(p: ProjectItem): FormData['projects'][number] {
  return {
    name: p.name, description: p.description, bullets: rows(p.bullets),
    tools_and_skills: joinList(p.tools_and_skills), link: str(p.link), proof_id: p.proof_id,
  }
}

export function sectionItemForm(e: SectionItem): FormData['sections'][number]['entries'][number] {
  return {
    title: e.title, organization: e.organization, location: str(e.location),
    start_date: str(e.start_date), end_date: str(e.end_date), is_current: e.is_current,
    description: e.description, bullets: rows(e.bullets), link: str(e.link), proof_id: e.proof_id,
  }
}

export function toFormValues(resume: Resume): ResumeFormValues {
  const { data } = resume
  const p = data.personal_info
  return {
    title: resume.title,
    type: resume.type,
    template: resume.template,
    target_role_id: resume.target_role?.id ?? null,
    experience_level: resume.experience_level ?? null,
    data: {
      personal_info: {
        full_name: p.full_name, headline: p.headline, email: str(p.email), phone: str(p.phone),
        location: str(p.location),
        profile_links: (p.profile_links ?? []).map((link) => ({ ...link })),
      },
      summary: data.summary,
      experience: data.experience.map((e) => ({
        company: e.company, title: e.title, location: str(e.location),
        start_date: str(e.start_date), end_date: str(e.end_date), is_current: e.is_current,
        bullets: rows(e.bullets), tools_and_skills: joinList(e.tools_and_skills),
      })),
      education: data.education.map((e) => ({
        institution: e.institution, degree: e.degree, field_of_study: str(e.field_of_study),
        grade: str(e.grade), start_date: str(e.start_date), end_date: str(e.end_date),
        is_current: e.is_current, bullets: rows(e.bullets),
      })),
      projects: data.projects.map(projectForm),
      skills: data.skills.map((s) => ({ ...s })),
      certifications: data.certifications.map((c) => ({
        name: c.name, issuer: str(c.issuer), issue_date: str(c.issue_date),
        credential_id: str(c.credential_id), credential_url: str(c.credential_url),
        proof_id: c.proof_id,
      })),
      achievements: rows(data.achievements),
      show_verified_skills: data.show_verified_skills ?? false,
      sections: (data.sections ?? []).map((s) => ({
        id: s.id, kind: s.kind, title: str(s.title),
        entries: s.entries.map(sectionItemForm),
      })),
    },
  }
}

const orNull = (value: string) => value.trim() || null
const cleanRows = (values: { value: string }[]) =>
  values.map((row) => row.value.trim()).filter(Boolean)
const splitList = (value: string) =>
  value.split(',').map((item) => item.trim()).filter(Boolean)

/** Form values -> API ResumeData. Drops blank bullets/skills so drafts always save. */
export function toResumeData(values: ResumeFormValues): ResumeData {
  const { data } = values
  const p = data.personal_info
  return {
    personal_info: {
      full_name: p.full_name.trim(), headline: p.headline.trim(), email: orNull(p.email),
      phone: orNull(p.phone), location: orNull(p.location),
      profile_links: p.profile_links
        .map((link) => ({ label: link.label.trim(), url: link.url.trim() }))
        .filter((link) => link.label && link.url),
    },
    summary: data.summary.trim(),
    experience: data.experience.map((e) => ({
      company: e.company.trim(), title: e.title.trim(), location: orNull(e.location),
      start_date: orNull(e.start_date), end_date: e.is_current ? null : orNull(e.end_date),
      is_current: e.is_current, bullets: cleanRows(e.bullets), tools_and_skills: splitList(e.tools_and_skills),
    })),
    education: data.education.map((e) => ({
      institution: e.institution.trim(), degree: e.degree.trim(),
      field_of_study: orNull(e.field_of_study), grade: orNull(e.grade),
      start_date: orNull(e.start_date), end_date: e.is_current ? null : orNull(e.end_date),
      is_current: e.is_current, bullets: cleanRows(e.bullets),
    })),
    projects: data.projects.map((p) => ({
      name: p.name.trim(), description: p.description.trim(), bullets: cleanRows(p.bullets),
      tools_and_skills: splitList(p.tools_and_skills), link: orNull(p.link), proof_id: p.proof_id,
    })),
    skills: data.skills
      .filter((s) => s.name.trim())
      .map((s) => ({ name: s.name.trim(), skill_id: s.skill_id, proof_id: s.proof_id })),
    certifications: data.certifications.map((c) => ({
      name: c.name.trim(), issuer: orNull(c.issuer), issue_date: orNull(c.issue_date),
      credential_id: orNull(c.credential_id), credential_url: orNull(c.credential_url),
      proof_id: c.proof_id,
    })),
    achievements: cleanRows(data.achievements),
    show_verified_skills: data.show_verified_skills,
    sections: data.sections.map(
      (s): SectionConfig => ({
        id: s.id, kind: s.kind, title: orNull(s.title),
        entries: s.entries.map((e) => ({
          title: e.title.trim(), organization: e.organization.trim(), location: orNull(e.location),
          start_date: orNull(e.start_date), end_date: e.is_current ? null : orNull(e.end_date),
          is_current: e.is_current, description: e.description.trim(), bullets: cleanRows(e.bullets),
          link: orNull(e.link), proof_id: e.proof_id,
        })),
      }),
    ),
  }
}

export function toPayload(values: ResumeFormValues): Required<ResumeUpdate> {
  return {
    title: values.title.trim(),
    type: values.type as ResumeType,
    template: values.template as ResumeTemplate,
    target_role_id: values.target_role_id,
    experience_level: values.experience_level,
    data: toResumeData(values),
  }
}
