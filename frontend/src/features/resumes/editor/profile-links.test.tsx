import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm } from 'react-hook-form'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/features/auth/auth-context'
import type { User } from '@/features/auth/types'
import { testUser } from '@/features/auth/test-user'
import type { TargetRole } from '@/features/target-roles/api'
import { api } from '@/lib/api'

import type { ResumeFormValues } from '../form-schema'
import { ProfileLinksField } from './profile-links'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))

const role = (id: string, industry: string, profile_links: string[]): TargetRole => ({
  id,
  name: id,
  slug: id,
  description: '',
  seniority: 'mid',
  source: 'curated',
  industry: { slug: industry.toLowerCase(), name: industry, recommended_template: 'classic', profile_links },
})
const ROLES = [
  role('nurse', 'Healthcare', ['LinkedIn', 'Personal website']),
  role('researcher', 'Research & Academia', ['LinkedIn', 'ORCID', 'Google Scholar']),
]
const TYPES = [
  { label: 'LinkedIn', placeholder: 'linkedin.com/in/your-name' },
  { label: 'ORCID', placeholder: 'orcid.org/0000-0000-0000-0000' },
]

function Harness({ roleId, links = [] }: { roleId: string | null; links?: { label: string; url: string }[] }) {
  const form = useForm<ResumeFormValues>({
    defaultValues: { target_role_id: roleId, data: { personal_info: { profile_links: links } } } as unknown as ResumeFormValues,
  })
  return (
    <FormProvider {...form}>
      <ProfileLinksField />
    </FormProvider>
  )
}

const USER: User = testUser()

function renderField(roleId: string | null, links?: { label: string; url: string }[], user: Partial<User> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const auth = {
    status: 'authenticated', user: { ...USER, ...user }, login: vi.fn(), register: vi.fn(), logout: vi.fn(),
    updateUser: vi.fn(), startSession: vi.fn(), endSession: vi.fn(),
  } as AuthContextValue
  render(
    <AuthContext.Provider value={auth}>
      <QueryClientProvider client={client}>
        <Harness roleId={roleId} links={links} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  )
}

beforeEach(() => {
  vi.mocked(api.get).mockImplementation(async (url: string) => ({
    data: url === '/target-roles' ? ROLES : { kinds: [], profile_links: TYPES },
  }))
})

describe('ProfileLinksField', () => {
  it('suggests the links that suit the role’s field', async () => {
    renderField('researcher')
    expect(await screen.findByText('Suggested for Research & Academia:')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ORCID' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Google Scholar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'GitHub' })).not.toBeInTheDocument()
  })

  it('never offers GitHub to a nurse', async () => {
    renderField('nurse')
    expect(await screen.findByText('Suggested for Healthcare:')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'LinkedIn' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Personal website' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'GitHub' })).not.toBeInTheDocument()
  })

  it('falls back to LinkedIn and a website without a role', () => {
    renderField(null)
    expect(screen.getByRole('button', { name: 'LinkedIn' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Personal website' })).toBeInTheDocument()
  })

  it('adds a suggested link as a row and stops suggesting it', async () => {
    renderField('researcher')
    await userEvent.click(await screen.findByRole('button', { name: 'ORCID' }))

    expect(screen.getByLabelText('Site')).toHaveValue('ORCID')
    expect(await screen.findByPlaceholderText('orcid.org/0000-0000-0000-0000')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ORCID' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove ORCID' }))
    expect(screen.queryByLabelText('Site')).not.toBeInTheDocument()
  })

  it('shows existing links and hides their suggestion', async () => {
    renderField('nurse', [{ label: 'LinkedIn', url: 'linkedin.com/in/amy' }])
    expect(screen.getByLabelText('Address')).toHaveValue('linkedin.com/in/amy')
    expect(await screen.findByText('Suggested for Healthcare:')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'LinkedIn' })).not.toBeInTheDocument()
  })

  it('pre-fills the LinkedIn profile a LinkedIn user signed in with', async () => {
    renderField('nurse', [], { linkedin_connected: true, linkedin_url: 'https://www.linkedin.com/in/priya-shah/' })
    expect(await screen.findByText('Add the LinkedIn profile you signed in with?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add linkedin.com/in/priya-shah' }))

    expect(screen.getByLabelText('Site', { selector: 'input' })).toHaveValue('LinkedIn')
    expect(screen.getByLabelText('Address', { selector: 'input' })).toHaveValue('linkedin.com/in/priya-shah')
    expect(screen.queryByText(/signed in with/)).not.toBeInTheDocument()
  })

  it('asks a LinkedIn user for the URL LinkedIn did not share', async () => {
    renderField('nurse', [], { linkedin_connected: true })
    expect(await screen.findByText(/LinkedIn doesn’t share it at sign-in/)).toBeInTheDocument()
    // Offered once, not also as a suggestion chip.
    expect(screen.getAllByRole('button', { name: /LinkedIn/ })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Add LinkedIn' }))
    expect(screen.getByLabelText('Address', { selector: 'input' })).toHaveValue('')
  })

  it('does not nag users who did not sign in with LinkedIn', async () => {
    renderField('nurse')
    expect(await screen.findByText('Suggested for Healthcare:')).toBeInTheDocument()
    expect(screen.queryByText(/signed in with/)).not.toBeInTheDocument()
  })
})
