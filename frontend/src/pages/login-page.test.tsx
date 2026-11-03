import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, AxiosHeaders } from 'axios'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/features/auth/auth-context'
import { ThemeProvider } from '@/features/theme/theme-provider'

import { LoginPage } from './login-page'

function renderLogin(login: AuthContextValue['login'], entry = '/login') {
  const auth: AuthContextValue = { status: 'unauthenticated', user: null, login, register: vi.fn(), logout: vi.fn(), updateUser: vi.fn(), startSession: vi.fn(), endSession: vi.fn() }
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/dashboard', element: <h1>Dashboard</h1> },
    ],
    { initialEntries: [entry] },
  )
  render(
    <ThemeProvider>
      <AuthContext.Provider value={auth}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </ThemeProvider>,
  )
  return router
}

describe('LoginPage', () => {
  it('validates before calling the API', async () => {
    const login = vi.fn()
    renderLogin(login)

    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findAllByText(/email|password/i)).not.toHaveLength(0)
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
    expect(login).not.toHaveBeenCalled()
  })

  it('signs in and goes to the dashboard', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    renderLogin(login)

    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith({ email: 'ada@example.com', password: 'password123' })
  })

  it('shows a friendly message for wrong credentials', async () => {
    const response = { status: 401, data: {}, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } }
    const login = vi.fn().mockRejectedValue(new AxiosError('401', 'ERR_BAD_REQUEST', undefined, null, response))
    renderLogin(login)

    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument()
  })

  it('offers Google, LinkedIn and GitHub, in that order, before email', () => {
    renderLogin(vi.fn())

    const providers = screen.getAllByRole('link', { name: /^Continue with/ })
    expect(providers.map((a) => a.textContent?.trim())).toEqual([
      'Continue with Google',
      'Continue with LinkedIn',
      'Continue with GitHub',
    ])
    expect(providers.map((a) => a.getAttribute('href')?.replace(/^.*\/auth\//, ''))).toEqual([
      'google/login',
      'linkedin/login',
      'github/login',
    ])
    // The email form comes after them.
    const github = providers[2]
    expect(github.compareDocumentPosition(screen.getByLabelText('Email')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it.each([
    ['linkedin_not_configured', "LinkedIn sign-in isn't set up on this server yet. Use another option."],
    ['google', "Google sign-in didn't complete. Please try again."],
  ])('explains the %s error', (error, message) => {
    renderLogin(vi.fn(), `/login?error=${error}`)

    expect(screen.getByText(message)).toBeInTheDocument()
  })
})
