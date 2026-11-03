import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, refreshSession, setAccessToken, setSessionExpiredHandler } from '@/lib/api'

import { AuthContext, type AuthContextValue, type AuthState } from './auth-context'
import type { LoginValues, RegisterValues } from './schemas'
import type { TokenResponse } from './types'

const signedOut: AuthState = { status: 'unauthenticated', user: null }

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>({ status: 'loading', user: null })

  const startSession = useCallback((data: TokenResponse) => {
    setAccessToken(data.access_token)
    setState({ status: 'authenticated', user: data.user })
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(() => {
      queryClient.clear()
      setState(signedOut)
    })
    // Restore the session from the refresh cookie (also completes GitHub login).
    refreshSession()
      .then(startSession)
      .catch(() => setState(signedOut))
    return () => setSessionExpiredHandler(null)
  }, [queryClient, startSession])

  const endSession = useCallback(() => {
    setAccessToken(null)
    queryClient.clear()
    setState(signedOut)
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login: async (values: LoginValues) => {
        const { data } = await api.post<TokenResponse>('/auth/login', values)
        startSession(data)
      },
      register: async ({ name, email, password }: RegisterValues) => {
        const { data } = await api.post<TokenResponse>('/auth/register', { name, email, password })
        startSession(data)
      },
      logout: async () => {
        try {
          await api.post('/auth/logout')
        } finally {
          endSession()
        }
      },
      updateUser: (user) => setState({ status: 'authenticated', user }),
      startSession,
      endSession,
    }),
    [state, startSession, endSession],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
