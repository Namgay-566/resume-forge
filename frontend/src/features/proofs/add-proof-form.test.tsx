import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import { AddProofForm } from './add-proof-form'
import type { CatalogSkill } from './types'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))

const CATALOG: CatalogSkill[] = [
  { id: 's1', name: 'Nursing License', slug: 'nursing-license', category: 'license', proof_types: ['professional_license', 'certificate'] },
  { id: 's2', name: 'Spreadsheets', slug: 'spreadsheets', category: 'tool', proof_types: ['work_sample', 'certificate'] },
]

function renderForm(props: Partial<Parameters<typeof AddProofForm>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddProofForm preselectSlug={null} bare {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async (url: string) => ({ data: url === '/skills' ? CATALOG : [] }))
  vi.mocked(api.post).mockReset()
})

describe('AddProofForm', () => {
  it('suggests the proof type that fits the skill', async () => {
    renderForm({ preselectSlug: 'nursing-license' })

    // Once the skills catalog loads, the skill's best proof type is selected.
    await waitFor(() => expect(screen.getByRole('radio', { name: /Licence or registration/ })).toBeChecked())
    expect(screen.getByText(/Best for Nursing License: licence or registration/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Link to your public register entry/)).toBeInTheDocument()
  })

  it('is honest about what each type can reach', async () => {
    renderForm()

    await userEvent.click(await screen.findByRole('radio', { name: /Work sample/ }))

    expect(screen.getByText(/Counts as self-reported at most: we can’t confirm you produced an uploaded file/)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Portfolio link.*Up to partially verified/ })).toBeInTheDocument()
  })

  it('uploads a licence with its register link', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { id: 'p1' } })
    renderForm({ preselectSlug: 'nursing-license', preselectType: 'professional_license' })
    const file = new File(['%PDF-1.7'], 'nmc.pdf', { type: 'application/pdf' })

    await userEvent.upload(await screen.findByLabelText('Licence or registration file'), file)
    await userEvent.type(screen.getByLabelText(/public register entry/), 'https://www.nmc.org.uk/register/123')
    await userEvent.click(screen.getByRole('button', { name: 'Upload licence or registration' }))

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const [url, form] = vi.mocked(api.post).mock.calls[0] as [string, FormData]
    expect(url).toBe('/proofs/upload')
    expect(form.get('type')).toBe('professional_license')
    expect(form.get('register_url')).toBe('https://www.nmc.org.uk/register/123')
    expect(form.getAll('skill_ids')).toEqual(['s1'])
  })

  it('requires skills for a work sample', async () => {
    renderForm({ preselectType: 'work_sample' })
    const file = new File(['PK'], 'plan.docx')

    await userEvent.upload(await screen.findByLabelText('Work sample file'), file)
    await userEvent.click(screen.getByRole('button', { name: 'Upload work sample' }))

    expect(await screen.findByText('Choose at least one skill it shows.')).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('accepts a DOI for publications', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { id: 'p2' } })
    renderForm({ preselectSlug: 'spreadsheets', preselectType: 'publication' })

    await userEvent.type(await screen.findByLabelText('DOI or link'), '10.1234/falls.2024')
    await userEvent.click(screen.getByRole('button', { name: 'Check publication' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/proofs', { type: 'publication', url: '10.1234/falls.2024', skill_ids: ['s2'] }))
  })
})
