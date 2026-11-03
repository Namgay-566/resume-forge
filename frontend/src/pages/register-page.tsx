import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { SubmitButton } from '@/components/submit-button'
import { apiErrorMessage } from '@/features/auth/api-error'
import { AuthLayout } from '@/features/auth/auth-layout'
import { FormError } from '@/features/auth/form-error'
import { FormField } from '@/components/form-field'
import { registerSchema, type RegisterValues } from '@/features/auth/schemas'
import { safeNextPath } from '@/features/auth/next-path'
import { useAuth } from '@/features/auth/use-auth'
import { useDocumentTitle } from '@/lib/use-document-title'

export function RegisterPage() {
  const { register: registerUser } = useAuth()
  useDocumentTitle('Create your account')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = safeNextPath(searchParams.get('next'))
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      await registerUser(values)
      navigate(next ?? '/dashboard', { replace: true })
    } catch (error) {
      setServerError(
        apiErrorMessage(error, { 409: 'An account with this email already exists. Try logging in.' }),
      )
    }
  })

  return (
    <AuthLayout
      title="Create your account"
      description="Build an ATS-friendly resume and close your skill gaps."
      footer={
        <>
          Already have an account?{' '}
          <Link to={next ? `/login?next=${encodeURIComponent(next)}` : '/login'} className="font-medium text-foreground underline-offset-4 hover:underline">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <FormError message={serverError} />
        <FormField label="Name" autoComplete="name" registration={register('name')} error={errors.name} />
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
          autoComplete="new-password"
          registration={register('password')}
          error={errors.password}
        />
        <FormField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          registration={register('confirmPassword')}
          error={errors.confirmPassword}
        />
        <SubmitButton pending={isSubmitting} pendingText="Creating account…" className="w-full">
          Create account
        </SubmitButton>
      </form>
    </AuthLayout>
  )
}
