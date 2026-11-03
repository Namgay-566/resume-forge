import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import type { Industry, TargetRole } from './api'
import { RolePicker } from './role-picker'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/lib/notify', () => ({ notifySuccess: vi.fn() }))

const INDUSTRIES: Industry[] = [
  { id: '1', slug: 'healthcare', name: 'Healthcare', description: '' },
  { id: '2', slug: 'skilled-trades', name: 'Skilled Trades', description: '' },
]
const role = (id: string, name: string, industry: Industry, source: TargetRole['source'] = 'curated'): TargetRole => ({
  id,
  name,
  slug: id,
  description: '',
  seniority: 'mid',
  source,
  industry: { slug: industry.slug, name: industry.name, recommended_template: 'classic', profile_links: [] },
})
const ROLES = [role('rn', 'Registered Nurse', INDUSTRIES[0]), role('elec', 'Electrician', INDUSTRIES[1])]

function Harness({ initial = null }: { initial?: string | null }) {
  const [value, setValue] = useState<string | null>(initial)
  return (
    <>
      <label htmlFor="picker">Target role</label>
      <RolePicker id="picker" value={value} onChange={setValue} />
      <output data-testid="value">{value ?? ''}</output>
    </>
  )
}

function renderPicker(initial: string | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <Harness initial={initial} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async (url: string) => ({
    data: url === '/industries' ? INDUSTRIES : ROLES,
  }))
  vi.mocked(api.post).mockReset()
})

describe('RolePicker', () => {
  it('autocompletes as you type and picks with the keyboard', async () => {
    renderPicker()
    const input = screen.getByRole('combobox', { name: 'Target role' })

    await userEvent.type(input, 'nur')
    expect(await screen.findByRole('option', { name: /Registered Nurse/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Electrician/ })).not.toBeInTheDocument()

    await userEvent.keyboard('{Enter}')
    expect(screen.getByTestId('value')).toHaveTextContent('rn')
    expect(input).toHaveValue('Registered Nurse')
    expect(screen.getByText('Healthcare · Mid level')).toBeInTheDocument()
  })

  it('browses by industry', async () => {
    renderPicker()
    await userEvent.click(screen.getByRole('combobox', { name: 'Target role' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Skilled Trades' }))

    expect(screen.getByRole('button', { name: 'Skilled Trades' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Electrician'])
  })

  it("creates a role the library doesn't have, and says it's AI-generated", async () => {
    const created = { ...role('vn', 'Veterinary Nurse', INDUSTRIES[0], 'ai_generated'), skills: [] }
    vi.mocked(api.post).mockResolvedValue({ data: { role: created, created: true } })
    renderPicker()

    await userEvent.type(screen.getByRole('combobox', { name: 'Target role' }), 'Veterinary Nurse')
    await userEvent.click(await screen.findByRole('option', { name: /Can't find your role\? Use “Veterinary Nurse”/ }))

    expect(api.post).toHaveBeenCalledWith('/target-roles/custom', { title: 'Veterinary Nurse', industry: null })
    await waitFor(() => expect(screen.getByTestId('value')).toHaveTextContent('vn'))
    expect(screen.getByText('AI-generated role.')).toBeInTheDocument()
  })

  it('offers to create only when the title is new', async () => {
    renderPicker()

    await userEvent.type(screen.getByRole('combobox', { name: 'Target role' }), 'electrician')

    expect(await screen.findByRole('option', { name: /Electrician/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Can't find your role/ })).not.toBeInTheDocument()
  })

  it('shows the AI budget message when generation is refused', async () => {
    const { AxiosError, AxiosHeaders } = await import('axios')
    const error = new AxiosError('limit', 'ERR', undefined, undefined, {
      status: 429,
      data: { detail: 'limit' },
      statusText: '',
      headers: {},
      config: { headers: new AxiosHeaders() },
    })
    vi.mocked(api.post).mockRejectedValue(error)
    renderPicker()

    await userEvent.type(screen.getByRole('combobox', { name: 'Target role' }), 'Beekeeper{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent(/AI allowance/)
    expect(screen.getByTestId('value')).toHaveTextContent('')
  })
})
