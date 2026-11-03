import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import type { TokenResponse } from '@/features/auth/types'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { 'Content-Type': 'application/json' },
  // Sends the httpOnly refresh cookie to /auth/* endpoints.
  withCredentials: true,
})

// Kept in memory only (never localStorage) so injected scripts can't read it at rest.
let accessToken: string | null = null
let onSessionExpired: (() => void) | null = null
let refreshInFlight: Promise<TokenResponse> | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<TokenResponse> {
  refreshInFlight ??= api
    .post<TokenResponse>('/auth/refresh')
    .then(({ data }) => {
      setAccessToken(data.access_token)
      return data
    })
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
}

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as RetriableConfig | undefined
  const isAuthCall = config?.url?.startsWith('/auth/') ?? false

  if (error.response?.status !== 401 || !config || config._retried || isAuthCall) {
    throw error
  }

  config._retried = true
  try {
    await refreshSession()
  } catch {
    setAccessToken(null)
    onSessionExpired?.()
    throw error
  }
  return api(config)
})
