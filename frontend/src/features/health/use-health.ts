import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

export interface HealthResponse {
  status: 'ok'
  app: string
  environment: string
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data } = await api.get<HealthResponse>('/health')
      return data
    },
  })
}
