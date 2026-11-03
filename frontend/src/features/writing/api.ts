import { useMutation } from '@tanstack/react-query'

import type { SectionKind } from '@/features/resumes/types'
import { api } from '@/lib/api'

import type { TailorResult, WritingOption } from './types'

export interface ImproveBulletInput {
  text: string
  /** Any section with bullets: experience, clinical placements, volunteering, custom... */
  section: SectionKind
  /** The user's heading for the section, if renamed (always set for custom sections). */
  section_title: string | null
  position: string
  tools_and_skills: string[]
}

export function useImproveBullet(resumeId: string) {
  return useMutation({
    mutationFn: async (input: ImproveBulletInput) =>
      (await api.post<{ options: WritingOption[] }>(`/resumes/${resumeId}/ai/improve-bullet`, input))
        .data.options,
  })
}

export function useGenerateSummary(resumeId: string) {
  return useMutation({
    mutationFn: async () =>
      (await api.post<{ options: WritingOption[] }>(`/resumes/${resumeId}/ai/summary`)).data.options,
  })
}

export function useTailor(resumeId: string) {
  return useMutation({
    mutationFn: async (jobDescription: string) =>
      (await api.post<TailorResult>(`/resumes/${resumeId}/ai/tailor`, { job_description: jobDescription }))
        .data,
  })
}
