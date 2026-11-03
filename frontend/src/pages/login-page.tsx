import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'

import { SubmitButton } from '@/components/submit-button'
import { apiErrorMessage } from '@/features/auth/api-error'
import { AuthLayout } from '@/features/auth/auth-layout'
import { PROVIDERS } from '@/features/auth/providers'
import { FormError } from '@/features/auth/form-error'
import { FormField } from '@/components/form-field'
import { loginSchema, type LoginValues } from '@/features/auth/schemas'
import { safeNextPath } from '@/features/auth/next-path'
import { useAuth } from '@/features/auth/use-auth'
import { useDocumentTitle } from '@/lib/use-document-title'

const OAUTH_ERRORS: Record<string, string> = Object.fromEntries(
  PROVIDERS.flatMap(({ id, label }) => [
    [id, `${label} sign-in didn't complete. Please try again.`],
    [`${id}_not_configured`, `${label} sign-in isn't set up on this server yet. Use another option.`],
  ]),
)

export function LoginPage() {
  const { login } = useAuth()
  useDocumentTitle('Log in')
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const oauthError = OAUTH_ERRORS[searchParams.get('error') ?? ''] ?? null
  const [serverError, setServerError] = useState<string | null>(oauthError)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      await login(values)
      const from = (location.state as { from?: string } | null)?.from
      navigate(safeNextPath(from, searchParams.get('next')) ?? '/dashboard', { replace: true })
    } catch (error) {
      setServerError(apiErrorMessage(error, { 401: 'Invalid email or password.' }))
    }
  })

  return (
    <AuthLayout
      title="Log in"
      description="Welcome back. Pick up where you left off."
      footer={
        <>
          New to ResumeForge?{' '}
          <Link to="/register" className="font-medium text-foreground underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormError message={serverError} />
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          registration={register('email')}
          error={errors.email}
        />
        <FormField
          label="Password"
          type="password"
          autoComplete="current-password"
          registration={register('password')}
          error={errors.password}
        />
        <SubmitButton pending={isSubmitting} pendingText="Logging in…" className="w-full">
          Log in
        </SubmitButton>
      </form>
    </AuthLayout>
  )
}
