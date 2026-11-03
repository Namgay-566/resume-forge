import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { api } from '@/lib/api'

import { isRunning, type CatalogSkill, type Proof, type ProofDetail } from './types'

const POLL_MS = 2500
const keys = {
  list: ['proofs'] as const,
  detail: (id: string) => ['proofs', id] as const,
}

/** A finished proof can verify skills, which changes readiness, the roadmap, the dashboard
 * and what the editor suggests adding to a resume. */
export function refreshSkillViews(queryClient: QueryClient) {
  for (const key of [['skill-gap'], ['roadmap'], ['dashboard'], ['resume-suggestions']]) {
    void queryClient.invalidateQueries({ queryKey: key })
  }
}

export function useProofs() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: keys.list,
    queryFn: async () => (await api.get<Proof[]>('/proofs')).data,
    // Keep polling while anything is still being analysed.
    refetchInterval: (query) => (query.state.data?.some((p) => isRunning(p.status)) ? POLL_MS : false),
  })
  // When any proof finishes, everything derived from verified skills is stale.
  const running = useRef<Set<string>>(new Set())
  useEffect(() => {
    if (!query.data) return
    const now = new Set(query.data.filter((p) => isRunning(p.status)).map((p) => p.id))
    if ([...running.current].some((id) => !now.has(id))) refreshSkillViews(queryClient)
    running.current = now
  }, [query.data, queryClient])
  return query
}

export function useProof(id: string) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: keys.detail(id),
    queryFn: async () => (await api.get<ProofDetail>(`/proofs/${id}`)).data,
    refetchInterval: (q) => (q.state.data && isRunning(q.state.data.status) ? POLL_MS : false),
    retry: false,
  })
  const status = query.data?.status
  const previous = useRef(status)
  useEffect(() => {
    if (previous.current && isRunning(previous.current) && status && !isRunning(status)) {
      refreshSkillViews(queryClient)
      void queryClient.invalidateQueries({ queryKey: keys.list })
    }
    previous.current = status
  }, [status, queryClient])
  return query
}

interface CreateProofBody {
  type: 'github_repo' | 'live_link' | 'portfolio_link' | 'publication'
  /** A URL, or a DOI for publications. */
  url: string
  skill_ids: string[]
  linked_proof_id?: string | null
}

export function useCreateProof() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateProofBody) => (await api.post<ProofDetail>('/proofs', body)).data,
    onSuccess: (proof) => {
      queryClient.setQueryData(keys.detail(proof.id), proof)
      void queryClient.invalidateQueries({ queryKey: keys.list })
      refreshSkillViews(queryClient) // claimed skills now show "proof being reviewed"
    },
  })
}

export function useReanalyze(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post<ProofDetail>(`/proofs/${id}/reanalyze`)).data,
    onSuccess: (proof) => {
      queryClient.setQueryData(keys.detail(id), proof)
      void queryClient.invalidateQueries({ queryKey: keys.list })
    },
  })
}

export function useSkillsCatalog() {
  return useQuery({
    queryKey: ['skills-catalog'],
    staleTime: 60 * 60 * 1000,
    queryFn: async () => (await api.get<CatalogSkill[]>('/skills')).data,
  })
}

export type UploadProofType = 'certificate' | 'professional_license' | 'work_sample' | 'reference_letter' | 'experience_letter'

interface UploadBody {
  type: UploadProofType
  file: File
  skillIds: string[]
  /** Licences: a link to your entry on the public register. */
  registerUrl?: string
}

/** File proofs: certificates, licences, work samples and letters. */
export function useUploadProof() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ type, file, skillIds, registerUrl }: UploadBody) => {
      const form = new FormData()
      form.append('type', type)
      form.append('file', file)
      for (const id of skillIds) form.append('skill_ids', id)
      if (registerUrl?.trim()) form.append('register_url', registerUrl.trim())
      return (await api.post<ProofDetail>('/proofs/upload', form, { headers: { 'Content-Type': undefined } })).data
    },
    onSuccess: (proof) => {
      queryClient.setQueryData(keys.detail(proof.id), proof)
      void queryClient.invalidateQueries({ queryKey: keys.list })
      refreshSkillViews(queryClient)
    },
  })
}

/** Uploaded files are only reachable through the authenticated API, so fetch them as blobs. */
export function useProofFileUrl(id: string, enabled: boolean) {
  const query = useQuery({
    queryKey: ['proofs', id, 'file'],
    enabled,
    staleTime: Infinity,
    queryFn: async () => {
      const response = await api.get<Blob>(`/proofs/${id}/file`, { responseType: 'blob' })
      return URL.createObjectURL(response.data)
    },
  })
  useEffect(() => {
    const url = query.data
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [query.data])
  return query
}
