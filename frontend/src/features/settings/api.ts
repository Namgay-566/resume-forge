import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { apiErrorMessage } from '@/features/auth/api-error'

import type { SignInProvider, TokenResponse, User, UserPreferences } from '@/features/auth/types'
import { useAuth } from '@/features/auth/use-auth'
import { api } from '@/lib/api'

export const settingsKeys = {
  emailChange: ['me', 'email-change'] as const,
}

export interface ProfileUpdate {
  name?: string
  linkedin_url?: string | null
}

export interface PasswordChange {
  current_password?: string
  new_password: string
}

export interface EmailChangePending {
  new_email: string
}

export interface AccountDelete {
  confirm_email: string
  current_password?: string
}

/** A mutation whose response is the updated user; puts it in the auth context. */
function useUserMutation<T>(request: (body: T) => Promise<User>) {
  const { updateUser } = useAuth()
  return useMutation({ mutationFn: request, onSuccess: (user) => updateUser(user) })
}

export function useUpdateProfile() {
  return useUserMutation(async (body: ProfileUpdate) => (await api.patch<User>('/me', body)).data)
}

export function useUpdatePreferences() {
  return useUserMutation(
    async (body: Partial<UserPreferences>) => (await api.patch<User>('/me/preferences', body)).data,
  )
}

/** Saves one preference as soon as it changes (Settings controls have no Save button). */
export function useSavePreference() {
  const update = useUpdatePreferences()
  return (change: Partial<UserPreferences>) =>
    update.mutate(change, {
      onSuccess: () => toast.success('Saved'),
      onError: (error) => toast.error(apiErrorMessage(error, {}, { useServerDetail: true })),
    })
}

export function useChangePassword() {
  const { startSession } = useAuth()
  return useMutation({
    mutationFn: async (body: PasswordChange) => (await api.post<TokenResponse>('/me/password', body)).data,
    // Every other device was signed out; this one continues on the new session.
    onSuccess: (tokens) => startSession(tokens),
  })
}

export function useSignOutEverywhere() {
  const { endSession } = useAuth()
  return useMutation({
    mutationFn: async () => {
      await api.post('/me/sign-out-everywhere')
    },
    onSuccess: () => endSession(),
  })
}

export function usePendingEmailChange() {
  return useQuery({
    queryKey: settingsKeys.emailChange,
    queryFn: async () => (await api.get<EmailChangePending | null>('/me/email-change')).data,
  })
}

export function useStartEmailChange() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { new_email: string; current_password?: string }) =>
      (await api.post<EmailChangePending>('/me/email-change', body)).data,
    onSuccess: (pending) => queryClient.setQueryData(settingsKeys.emailChange, pending),
  })
}

export function useConfirmEmailChange() {
  const queryClient = useQueryClient()
  const { updateUser } = useAuth()
  return useMutation({
    mutationFn: async (code: string) => (await api.post<User>('/me/email-change/confirm', { code })).data,
    onSuccess: (user) => {
      updateUser(user)
      queryClient.setQueryData(settingsKeys.emailChange, null)
    },
  })
}

export function useCancelEmailChange() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.delete('/me/email-change')
    },
    onSuccess: () => queryClient.setQueryData(settingsKeys.emailChange, null),
  })
}

export function useDisconnectProvider() {
  return useUserMutation(
    async (provider: SignInProvider) => (await api.delete<User>(`/me/providers/${provider}`)).data,
  )
}

/** Full-page redirect to the provider; it comes back to /settings?connected=… */
export function connectUrl(provider: SignInProvider): string {
  return `${import.meta.env.VITE_API_URL}/auth/${provider}/login?link=true`
}

export function useDeleteAccount() {
  const { endSession } = useAuth()
  return useMutation({
    mutationFn: async (body: AccountDelete) => {
      await api.post('/me/delete', body)
    },
    onSuccess: () => endSession(),
  })
}

function filenameFrom(disposition: string | undefined, fallback: string): string {
  const utf8 = disposition && /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  return utf8 ? decodeURIComponent(utf8[1]) : fallback
}

/** Download everything stored about the user as a ZIP. */
export function useExportData() {
  return useMutation({
    mutationFn: async () => {
      const response = await api.get<Blob>('/me/export', { responseType: 'blob' })
      const url = URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = filenameFrom(response.headers['content-disposition'], 'ResumeForge-data.zip')
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    },
  })
}
