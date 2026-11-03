import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/features/auth/auth-context'
import { testUser } from '@/features/auth/test-user'
import type { User } from '@/features/auth/types'
import { api } from '@/lib/api'

import { DangerZone } from './data-section'
import { EmailChange } from './email-change'
import { connectErrorMessage, isPlaceholderEmail, signInMethodCount } from './helpers'
import { NotificationsSection } from './preferences-sections'
import { SecuritySection } from './security-section'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }))

function renderWith(ui: ReactNode, user: User, auth: Partial<AuthContextValue> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const value = {
    status: 'authenticated',
    user,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    updateUser: vi.fn(),
    startSession: vi.fn(),
    endSession: vi.fn(),
    ...auth,
  } as AuthContextValue
  render(
    <MemoryRouter>
      <AuthContext.Provider value={value}>
        <QueryClientProvider client={client}>{ui}</QueryClientProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
  return value
}

beforeEach(() => {
  vi.mocked(api.get).mockResolvedValue({ data: null })
})

describe('settings helpers', () => {
  it('counts a password and each connected account as a way to sign in', () => {
    expect(signInMethodCount(testUser())).toBe(1)
    expect(signInMethodCount(testUser({ has_password: false, github_connected: true }))).toBe(1)
    expect(signInMethodCount(testUser({ google_connected: true, linkedin_connected: true }))).toBe(3)
  })

  it('recognises placeholder addresses from sign-in providers', () => {
    expect(isPlaceholderEmail('12+ada@users.noreply.github.com')).toBe(true)
    expect(isPlaceholderEmail('google-99@users.noreply.invalid')).toBe(true)
    expect(isPlaceholderEmail('ada@example.com')).toBe(false)
  })

  it('explains why connecting an account failed', () => {
    expect(connectErrorMessage('in_use')).toMatch(/different ResumeForge account/)
    expect(connectErrorMessage('github_not_configured')).toBe('GitHub sign-in isn’t set up on this server.')
    expect(connectErrorMessage('linkedin_session')).toMatch(/session ended/)
    expect(connectErrorMessage('google')).toBe('We couldn’t connect Google. Please try again.')
  })
})

describe('SecuritySection', () => {
  it('won’t disconnect the only way to sign in', () => {
    renderWith(<SecuritySection user={testUser({ has_password: false, github_connected: true })} />, testUser())

    expect(screen.getByRole('button', { name: 'Disconnect GitHub' })).toBeDisabled()
    expect(screen.getByText(/only way to sign in/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add password' })).toBeInTheDocument()
    // Not-yet-connected providers link to the backend's connect flow.
    expect(screen.getByRole('link', { name: 'Connect Google' })).toHaveAttribute(
      'href',
      expect.stringMatching(/\/auth\/google\/login\?link=true$/),
    )
  })

  it('changes the password and takes over the new session', async () => {
    const tokens = { access_token: 't', token_type: 'bearer', expires_in: 900, user: testUser() }
    vi.mocked(api.post).mockResolvedValue({ data: tokens })
    const auth = renderWith(<SecuritySection user={testUser()} />, testUser())

    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    await userEvent.type(screen.getByLabelText('Current password'), 'old password')
    await userEvent.type(screen.getByLabelText('New password'), 'short')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Use at least 8 characters')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()

    await userEvent.clear(screen.getByLabelText('New password'))
    await userEvent.type(screen.getByLabelText('New password'), 'a much better password')
    await userEvent.clear(screen.getByLabelText('Confirm new password'))
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'a much better password')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))

    await vi.waitFor(() => expect(auth.startSession).toHaveBeenCalledWith(tokens))
    expect(api.post).toHaveBeenCalledWith('/me/password', {
      current_password: 'old password',
      new_password: 'a much better password',
    })
  })
})

describe('EmailChange', () => {
  it('asks for the code once one was sent', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { new_email: 'new@example.com' } })
    renderWith(<EmailChange user={testUser()} />, testUser())

    expect(await screen.findByText('new@example.com')).toBeInTheDocument()
    expect(screen.getByLabelText('Code')).toBeInTheDocument()
  })

  it('offers to add an email when the provider shared none', async () => {
    const user = testUser({ email: '1+ada@users.noreply.github.com', has_password: false })
    renderWith(<EmailChange user={user} />, user)

    expect(await screen.findByRole('button', { name: 'Add email' })).toBeInTheDocument()
    expect(screen.getByText('No email yet')).toBeInTheDocument()
  })
})

describe('NotificationsSection', () => {
  it('saves the proof email choice straight away; security notices stay on', async () => {
    vi.mocked(api.patch).mockResolvedValue({ data: testUser() })
    renderWith(<NotificationsSection user={testUser()} />, testUser())

    await userEvent.click(screen.getByRole('checkbox', { name: /Proof results/ }))

    expect(api.patch).toHaveBeenCalledWith('/me/preferences', { email_proof_updates: false })
    expect(screen.getByRole('checkbox', { name: /Security notices/ })).toBeDisabled()
  })
})

describe('DangerZone', () => {
  it('only deletes after the email is typed exactly', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: null })
    const auth = renderWith(<DangerZone user={testUser()} />, testUser())

    await userEvent.click(screen.getByRole('button', { name: 'Delete account' }))
    await userEvent.type(screen.getByLabelText(/Type priya@example.com/), 'priya@example.org')
    await userEvent.type(screen.getByLabelText('Password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Delete forever' }))
    expect(await screen.findByText('Type your email address exactly as shown')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()

    await userEvent.clear(screen.getByLabelText(/Type priya@example.com/))
    await userEvent.type(screen.getByLabelText(/Type priya@example.com/), 'Priya@Example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Delete forever' }))

    await vi.waitFor(() => expect(auth.endSession).toHaveBeenCalled())
    expect(api.post).toHaveBeenCalledWith('/me/delete', {
      confirm_email: 'Priya@Example.com',
      current_password: 'secret',
    })
  })
})
