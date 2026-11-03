import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormField } from '@/components/form-field'
import { SubmitButton } from '@/components/submit-button'
import { Button } from '@/components/ui/button'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import type { User } from '@/features/auth/types'

import { useCancelEmailChange, useConfirmEmailChange, usePendingEmailChange, useStartEmailChange } from './api'
import { isPlaceholderEmail } from './helpers'
import { SettingRow } from './settings-section'

const startSchema = (needsPassword: boolean) =>
  z.object({
    new_email: z.email('Enter a valid email address'),
    current_password: needsPassword ? z.string().min(1, 'Enter your current password') : z.string(),
  })
type StartValues = z.infer<ReturnType<typeof startSchema>>

const codeSchema = z.object({ code: z.string().trim().regex(/^\d{6}$/, 'Enter the 6-digit code') })
type CodeValues = z.infer<typeof codeSchema>

const serverMessage = (error: unknown) => apiErrorMessage(error, {}, { useServerDetail: true })

/** Change the sign-in email: a code goes to the new address; nothing changes until it's entered. */
export function EmailChange({ user }: { user: User }) {
  const pending = usePendingEmailChange()
  const [editing, setEditing] = useState(false)
  const placeholder = isPlaceholderEmail(user.email)

  if (pending.data) return <ConfirmCode newEmail={pending.data.new_email} hasPassword={user.has_password} />

  return (
    <div className="flex flex-col">
      <SettingRow
        label="Email"
        hint={
          placeholder
            ? 'Your sign-in provider didn’t share an email, so we can’t send you anything. Add one you use.'
            : 'You sign in with it, and it’s where we send notices about your account.'
        }
      >
        <span className="truncate text-sm text-muted-foreground" title={user.email}>
          {placeholder ? 'No email yet' : user.email}
        </span>
        {!editing && (
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            {placeholder ? 'Add email' : 'Change'}
          </Button>
        )}
      </SettingRow>
      {editing && <StartForm hasPassword={user.has_password} onCancel={() => setEditing(false)} />}
    </div>
  )
}

function StartForm({ hasPassword, onCancel }: { hasPassword: boolean; onCancel: () => void }) {
  const start = useStartEmailChange()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<StartValues>({
    resolver: zodResolver(startSchema(hasPassword)),
    defaultValues: { new_email: '', current_password: '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    try {
      await start.mutateAsync({
        new_email: values.new_email,
        current_password: hasPassword ? values.current_password : undefined,
      })
    } catch {
      // Shown in the form.
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4 pb-4">
      <FormError message={start.error ? serverMessage(start.error) : null} />
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          label="New email"
          type="email"
          autoComplete="email"
          registration={register('new_email')}
          error={errors.new_email}
        />
        {hasPassword && (
          <FormField
            label="Current password"
            type="password"
            autoComplete="current-password"
            registration={register('current_password')}
            error={errors.current_password}
          />
        )}
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <SubmitButton pending={isSubmitting} pendingText="Sending…">
          Send code
        </SubmitButton>
      </div>
    </form>
  )
}

function ConfirmCode({ newEmail, hasPassword }: { newEmail: string; hasPassword: boolean }) {
  const confirm = useConfirmEmailChange()
  const cancel = useCancelEmailChange()
  const resend = useStartEmailChange()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CodeValues>({ resolver: zodResolver(codeSchema), defaultValues: { code: '' } })

  const onSubmit = handleSubmit(async ({ code }) => {
    try {
      await confirm.mutateAsync(code)
      toast.success(`Your email is now ${newEmail}`)
    } catch {
      // Shown in the form.
    }
  })

  const error = confirm.error ?? resend.error ?? cancel.error
  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4 py-4">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium">Confirm your new email</span>
        <span className="text-sm text-muted-foreground">
          We sent a 6-digit code to <strong className="font-medium text-foreground">{newEmail}</strong>. It expires in 15 minutes.
        </span>
      </div>
      <FormError message={error ? serverMessage(error) : null} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <FormField
            label="Code"
            inputMode="numeric"
            autoComplete="one-time-code"
            registration={register('code')}
            error={errors.code}
          />
        </div>
        <SubmitButton pending={isSubmitting} pendingText="Checking…">
          Confirm
        </SubmitButton>
        {/* A resend needs the password again when there is one, so offer "use a different email" instead. */}
        {!hasPassword && (
          <Button
            type="button"
            variant="ghost"
            disabled={resend.isPending}
            onClick={() =>
              resend.mutate({ new_email: newEmail }, { onSuccess: () => toast.success('New code sent') })
            }
          >
            Send a new code
          </Button>
        )}
        <Button type="button" variant="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
          {hasPassword ? 'Start again' : 'Cancel'}
        </Button>
      </div>
    </form>
  )
}
