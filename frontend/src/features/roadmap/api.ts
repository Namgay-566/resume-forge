import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { DashboardSummary, PlanStatus, ProjectIdea, Roadmap, RoadmapItem } from './types'

const roadmapKey = (resumeId: string | null) => ['roadmap', resumeId] as const
export const dashboardKey = ['dashboard'] as const

export function useRoadmap(resumeId: string | null) {
  return useQuery({
    queryKey: roadmapKey(resumeId),
    enabled: Boolean(resumeId),
    retry: false,
    queryFn: async () => (await api.get<Roadmap>(`/resumes/${resumeId}/roadmap`)).data,
  })
}

export function useDashboard() {
  return useQuery({
    queryKey: dashboardKey,
    queryFn: async () => (await api.get<DashboardSummary>('/dashboard')).data,
    // The home screen is visited often; reuse a recent result and refresh in the background.
    staleTime: 30_000,
  })
}

function recompute(roadmap: Roadmap, items: RoadmapItem[]): Roadmap {
  const total = items.reduce((sum, i) => sum + i.hours.total, 0)
  const remaining = items.filter((i) => i.plan_status !== 'done').reduce((sum, i) => sum + i.hours.total, 0)
  return {
    ...roadmap,
    items,
    totals: {
      items: items.length,
      done: items.filter((i) => i.plan_status === 'done').length,
      in_progress: items.filter((i) => i.plan_status === 'in_progress').length,
      hours_total: Math.round(total * 10) / 10,
      hours_remaining: Math.round(remaining * 10) / 10,
    },
  }
}

/** Optimistic: the page updates immediately and rolls back if the save fails. */
export function useSetPlanStatus(resumeId: string) {
  const queryClient = useQueryClient()
  const key = roadmapKey(resumeId)
  return useMutation({
    mutationFn: async ({ skillId, status }: { skillId: string; status: PlanStatus }) =>
      (await api.put(`/roadmap/${skillId}`, { status })).data,
    onMutate: async ({ skillId, status }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<Roadmap>(key)
      if (previous) {
        const items = previous.items.map((i) => (i.skill_id === skillId ? { ...i, plan_status: status } : i))
        queryClient.setQueryData(key, recompute(previous, items))
      }
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous)
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: dashboardKey }),
  })
}

export function useProjectIdea(resumeId: string) {
  const queryClient = useQueryClient()
  const key = roadmapKey(resumeId)
  return useMutation({
    mutationFn: async ({ skillId, regenerate }: { skillId: string; regenerate: boolean }) =>
      (
        await api.post<ProjectIdea>(`/resumes/${resumeId}/roadmap/${skillId}/project`, null, {
          params: { regenerate },
        })
      ).data,
    onSuccess: (project, { skillId }) => {
      const roadmap = queryClient.getQueryData<Roadmap>(key)
      if (!roadmap) return
      const items = roadmap.items.map((i) =>
        i.skill_id === skillId
          ? { ...i, project, hours: { ...i.hours, project: project.est_hours, total: i.hours.learn + project.est_hours } }
          : i,
      )
      queryClient.setQueryData(key, recompute(roadmap, items))
      void queryClient.invalidateQueries({ queryKey: dashboardKey })
    },
  })
}
