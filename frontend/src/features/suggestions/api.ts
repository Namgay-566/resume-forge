import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { ProjectDraft, ProofLinks, ResumeSuggestion } from './types'

export const suggestionsKey = (resumeId: string) => ['resume-suggestions', resumeId] as const

export function useResumeSuggestions(resumeId: string) {
  return useQuery({
    queryKey: suggestionsKey(resumeId),
    queryFn: async () =>
      (await api.get<{ suggestions: ResumeSuggestion[]; proof_links: ProofLinks }>(`/resumes/${resumeId}/suggestions`))
        .data,
  })
}

export function useDismissSuggestion(resumeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.post(`/resumes/${resumeId}/suggestions/${encodeURIComponent(id)}/dismiss`)
      return id
    },
    onSuccess: (id) =>
      queryClient.setQueryData<{ suggestions: ResumeSuggestion[]; proof_links: ProofLinks }>(
        suggestionsKey(resumeId),
        (old) => old && { ...old, suggestions: old.suggestions.filter((s) => s.id !== id) },
      ),
  })
}

export function useProjectDraft(resumeId: string) {
  return useMutation({
    mutationFn: async ({ proofId, regenerate }: { proofId: string; regenerate: boolean }) =>
      (
        await api.post<ProjectDraft>(`/resumes/${resumeId}/suggestions/project-draft`, {
          proof_id: proofId,
          regenerate,
        })
      ).data,
  })
}
