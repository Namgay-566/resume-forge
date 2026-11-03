import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ResumeTemplate } from '@/features/resumes/types'
import { api } from '@/lib/api'

export type ContentSource = 'curated' | 'ai_generated'
export type SkillImportance = 'critical' | 'important' | 'nice_to_have'

export interface Industry {
  id: string
  slug: string
  name: string
  description: string
}

export interface TargetRole {
  id: string
  name: string
  slug: string
  description: string
  seniority: string
  /** ai_generated roles were drafted by the AI from a job title the user typed. */
  source: ContentSource
  industry: { slug: string; name: string; recommended_template: ResumeTemplate; profile_links: string[] }
}

export interface TargetRoleDetail extends TargetRole {
  skills: { name: string; importance: SkillImportance }[]
}

export interface CustomRoleResult {
  role: TargetRoleDetail
  /** False when the title matched an existing role, so nothing new was generated. */
  created: boolean
}

export const targetRoleKeys = {
  list: ['target-roles'] as const,
  industries: ['industries'] as const,
  detail: (id: string) => ['target-roles', id] as const,
}

export function useTargetRoles() {
  return useQuery({
    queryKey: targetRoleKeys.list,
    queryFn: async () => (await api.get<TargetRole[]>('/target-roles')).data,
    staleTime: 60 * 60 * 1000, // curated library; the user's own additions are added on create
  })
}

export function useIndustries() {
  return useQuery({
    queryKey: targetRoleKeys.industries,
    queryFn: async () => (await api.get<Industry[]>('/industries')).data,
    staleTime: Infinity,
  })
}

export function useTargetRole(id: string | null | undefined) {
  return useQuery({
    queryKey: targetRoleKeys.detail(id ?? ''),
    queryFn: async () => (await api.get<TargetRoleDetail>(`/target-roles/${id}`)).data,
    enabled: Boolean(id),
    staleTime: 60 * 60 * 1000,
  })
}

/** Build a role for a job title that isn't in the library (the AI drafts its skills). */
export function useCreateCustomRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { title: string; industry?: string | null }) =>
      (await api.post<CustomRoleResult>('/target-roles/custom', body)).data,
    onSuccess: ({ role }) => {
      queryClient.setQueryData(targetRoleKeys.detail(role.id), role)
      queryClient.setQueryData<TargetRole[]>(targetRoleKeys.list, (roles) =>
        roles && !roles.some((r) => r.id === role.id) ? [...roles, role] : roles,
      )
    },
  })
}
