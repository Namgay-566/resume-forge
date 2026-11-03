import { PROVIDERS } from '@/features/auth/providers'
import type { SignInProvider, User } from '@/features/auth/types'

/** Placeholder addresses for accounts whose sign-in provider shared no email. */
export function isPlaceholderEmail(email: string): boolean {
  return /@users\.noreply\.github\.com$|\.invalid$/i.test(email)
}

export function isConnected(user: User, provider: SignInProvider): boolean {
  return { google: user.google_connected, linkedin: user.linkedin_connected, github: user.github_connected }[provider]
}

/** Password plus connected providers. The last one can't be removed. */
export function signInMethodCount(user: User): number {
  return Number(user.has_password) + PROVIDERS.filter(({ id }) => isConnected(user, id)).length
}

export const providerLabel = (id: string) => PROVIDERS.find((p) => p.id === id)?.label ?? 'That account'

/** Message for ?connect_error=… from the backend's OAuth callback (see routers/auth.py). */
export function connectErrorMessage(code: string): string {
  if (code === 'in_use') {
    return 'That account already signs in to a different ResumeForge account. Sign in with it and delete that account first, or use another one.'
  }
  const [provider, reason] = code.split('_', 2) as [string, string | undefined]
  const name = providerLabel(provider)
  if (reason === 'not') return `${name} sign-in isn’t set up on this server.`
  if (reason === 'session') return 'Your session ended before we could connect it. Sign in again and retry.'
  return `We couldn’t connect ${name}. Please try again.`
}
