import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from './auth-context'
import { RedirectIfAuthenticated } from './route-guards'

const signedIn = {
  status: 'authenticated',
  user: { id: 'u1', email: 'a@example.com', name: 'Ada', github_username: null, linkedin_connected: false, linkedin_url: null, created_at: '' },
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
} as unknown as AuthContextValue

function visit(url: string) {
  const router = createMemoryRouter(
    [
      { element: <RedirectIfAuthenticated />, children: [{ path: '/register', element: <p>form</p> }] },
      { path: '/dashboard', element: <h1>Dashboard</h1> },
      { path: '/resumes', element: <h1>Resumes</h1> },
    ],
    { initialEntries: [url] },
  )
  render(
    <AuthContext.Provider value={signedIn}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  )
  return router
}

describe('RedirectIfAuthenticated', () => {
  it('sends a signed-in user on to ?next= (landing CTAs)', async () => {
    const router = visit('/register?next=%2Fresumes%3Fimport%3D1')
    expect(await screen.findByRole('heading', { name: 'Resumes' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?import=1')
  })

  it('ignores external destinations', async () => {
    visit('/register?next=%2F%2Fevil.example')
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })
})
