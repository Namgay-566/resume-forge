import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'

import { resumeKeys } from '@/features/resumes/api'
import { dashboardKey } from '@/features/roadmap/api'
import { api } from '@/lib/api'

import type { AtsAnalysis } from './types'

const latestKey = (resumeId: string) => ['ats', 'latest', resumeId] as const

export function useLatestAnalysis(resumeId: string, enabled: boolean) {
  return useQuery({
    queryKey: latestKey(resumeId),
    enabled,
    queryFn: async () => {
      try {
        return (await api.get<AtsAnalysis>(`/resumes/${resumeId}/ats-analyses/latest`)).data
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null // never analysed
        throw error
      }
    },
  })
}

export function useRunAnalysis(resumeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    /** review: false re-scores without the AI review (free, for quick before/after checks). */
    mutationFn: async ({ jobDescription, review = true }: { jobDescription: string | null; review?: boolean }) =>
      (
        await api.post<AtsAnalysis>(`/resumes/${resumeId}/ats-analyses`, {
          job_description: jobDescription,
          review,
        })
      ).data,
    onSuccess: (analysis) => {
      queryClient.setQueryData(latestKey(resumeId), analysis)
      // The resume's saved ats_score and its score history changed.
      void queryClient.invalidateQueries({ queryKey: resumeKeys.list })
      void queryClient.invalidateQueries({ queryKey: dashboardKey })
    },
  })
}
