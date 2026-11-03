import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { ExperienceLevel, ResumeType, SectionKind } from '../types'

export interface FieldSpec {
  label: string
  placeholder: string | null
}

/** Which generic entry fields a kind shows, and their labels. Missing fields are hidden. */
export interface EntryFields {
  title: FieldSpec
  organization: FieldSpec | null
  location: FieldSpec | null
  dates: 'range' | 'single' | null
  description: FieldSpec | null
  bullets: FieldSpec | null
  link: FieldSpec | null
}

export interface KindSpec {
  kind: SectionKind
  heading: string
  standard_headings: string[]
  hint: string | null
  item_label: string
  counts_as_experience: boolean
  layout: 'entries' | 'inline'
  repeatable: boolean
  fields: EntryFields | null
}

export type SectionCatalog = Partial<Record<SectionKind, KindSpec>>

export interface ProfileLinkType {
  label: string
  placeholder: string
}

export interface SectionSuggestions {
  sections: SectionKind[]
  required: SectionKind[]
  role_name: string | null
}

async function fetchCatalog() {
  return (await api.get<{ kinds: KindSpec[]; profile_links: ProfileLinkType[] }>('/resume-sections')).data
}

/** Kinds of profile link (LinkedIn, ORCID...) with editor placeholders. */
export function useProfileLinkTypes() {
  return useQuery({ queryKey: ['resume-sections'], queryFn: fetchCatalog, staleTime: Infinity, select: (d) => d.profile_links })
}

/** Every section kind's heading, field labels and hints (static configuration). */
export function useSectionCatalog() {
  return useQuery({
    queryKey: ['resume-sections'],
    queryFn: fetchCatalog,
    staleTime: Infinity,
    select: (d) => Object.fromEntries(d.kinds.map((k) => [k.kind, k])) as SectionCatalog,
  })
}

/** Sections suggested for this role, career stage and document type, in order. */
export function useSectionSuggestions(roleId: string | null, level: ExperienceLevel | null, type: ResumeType) {
  return useQuery({
    queryKey: ['resume-sections', 'suggestions', roleId, level, type],
    queryFn: async () =>
      (
        await api.get<SectionSuggestions>('/resume-sections/suggestions', {
          params: { target_role_id: roleId ?? undefined, experience_level: level ?? undefined, type },
        })
      ).data,
    staleTime: 60 * 60 * 1000,
  })
}
