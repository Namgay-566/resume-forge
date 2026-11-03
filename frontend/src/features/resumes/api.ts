import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type {
  Resume,
  ResumeCreate,
  ResumeImportResult,
  ResumeSummary,
  ResumeUpdate,
} from './types'

export const resumeKeys = {
  list: ['resumes', 'list'] as const,
  detail: (id: string) => ['resumes', 'detail', id] as const,
}

export function useResumes() {
  return useQuery({
    queryKey: resumeKeys.list,
    queryFn: async () => (await api.get<ResumeSummary[]>('/resumes')).data,
  })
}

export function useResume(id: string) {
  return useQuery({
    queryKey: resumeKeys.detail(id),
    queryFn: async () => (await api.get<Resume>(`/resumes/${id}`)).data,
    // The editor owns the data while open; don't refetch over the user's typing.
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  })
}

export function useCreateResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ResumeCreate) => (await api.post<Resume>('/resumes', body)).data,
    onSuccess: (resume) => {
      queryClient.setQueryData(resumeKeys.detail(resume.id), resume)
      void queryClient.invalidateQueries({ queryKey: resumeKeys.list })
    },
  })
}

export function useDuplicateResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => (await api.post<Resume>(`/resumes/${id}/duplicate`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: resumeKeys.list }),
  })
}

export function useDeleteResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/resumes/${id}`)
      return id
    },
    onSuccess: (id) => {
      queryClient.removeQueries({ queryKey: resumeKeys.detail(id) })
      return queryClient.invalidateQueries({ queryKey: resumeKeys.list })
    },
  })
}

export function useUpdateResume(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ResumeUpdate) =>
      (await api.patch<Resume>(`/resumes/${id}`, body)).data,
    onSuccess: (resume) => {
      queryClient.setQueryData(resumeKeys.detail(id), resume)
      // Skills on the resume feed the gap, roadmap, dashboard and proof suggestions.
      for (const key of [resumeKeys.list, ['skill-gap'], ['roadmap'], ['dashboard'], ['resume-suggestions', id]]) {
        void queryClient.invalidateQueries({ queryKey: key })
      }
    },
  })
}

interface ImportVariables {
  file: File
  onUploadProgress: (fraction: number) => void
  signal: AbortSignal
}

export function useImportResume() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, onUploadProgress, signal }: ImportVariables) => {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post<ResumeImportResult>('/resumes/import', form, {
        // Let the browser set the multipart boundary.
        headers: { 'Content-Type': undefined },
        signal,
        onUploadProgress: (event) => {
          if (event.total) onUploadProgress(event.loaded / event.total)
        },
      })
      return data
    },
    onSuccess: ({ resume }) => {
      queryClient.setQueryData(resumeKeys.detail(resume.id), resume)
      void queryClient.invalidateQueries({ queryKey: resumeKeys.list })
    },
  })
}
