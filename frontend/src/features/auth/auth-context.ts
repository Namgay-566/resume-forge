import { createContext } from 'react'

import type { LoginValues, RegisterValues } from './schemas'
import type { TokenResponse, User } from './types'

export type AuthState =
  | { status: 'loading'; user: null }
  | { status: 'authenticated'; user: User }
  | { status: 'unauthenticated'; user: null }

export type AuthContextValue = AuthState & {
  login: (values: LoginValues) => Promise<void>
  register: (values: RegisterValues) => Promise<void>
  logout: () => Promise<void>
  /** Replace the signed-in user after a Settings change (profile, preferences, email). */
  updateUser: (user: User) => void
  /** Take over a fresh session the server issued (after a password change). */
  startSession: (data: TokenResponse) => void
  /** Forget the session locally; the server already ended it (sign out everywhere, delete). */
  endSession: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
