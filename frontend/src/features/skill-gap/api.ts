import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { LearningResource, SkillGapReport } from './types'

export function useSkillGap(resumeId: string | null) {
  return useQuery({
    queryKey: ['skill-gap', resumeId],
    enabled: Boolean(resumeId),
    queryFn: async () => (await api.get<SkillGapReport>(`/resumes/${resumeId}/skill-gap`)).data,
    retry: false,
  })
}

export function useLearningResources(skillId: string | null) {
  return useQuery({
    queryKey: ['learning-resources', skillId],
    enabled: Boolean(skillId),
    staleTime: 60 * 60 * 1000, // curated catalog, rarely changes
    queryFn: async () =>
      (await api.get<{ skill_name: string; resources: LearningResource[]; search_phrase: string }>(`/skills/${skillId}/learning-resources`))
        .data,
  })
}
