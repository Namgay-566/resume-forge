import { zodResolver } from '@hookform/resolvers/zod'
import { LogOut } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormField } from '@/components/form-field'
import { SubmitButton } from '@/components/submit-button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { PROVIDERS } from '@/features/auth/providers'
import type { User } from '@/features/auth/types'

import { connectUrl, useChangePassword, useDisconnectProvider, useSignOutEverywhere } from './api'
import { isConnected, signInMethodCount } from './helpers'
import { SettingRow, SettingsSection } from './settings-section'

const serverMessage = (error: unknown) => apiErrorMessage(error, {}, { useServerDetail: true })

export function SecuritySection({ user }: { user: User }) {
  return (
    <SettingsSection
      id="security"
      title="Sign-in and security"
      description="How you sign in to ResumeForge. Keep at least one way in."
    >
      <PasswordForm hasPassword={user.has_password} />
      <ConnectedAccounts user={user} />
      <SignOutEverywhere />
    </SettingsSection>
  )
}

// Mirrors the register rules (backend/app/schemas/auth.py).
const passwordSchema = (hasPassword: boolean) =>
  z
    .object({
      current_password: hasPassword ? z.string().min(1, 'Enter your current password') : z.string(),
      new_password: z.string().min(8, 'Use at least 8 characters').max(128, 'Use at most 128 characters'),
      confirm: z.string(),
    })
    .refine((v) => v.new_password === v.confirm, { message: 'Passwords do not match', path: ['confirm'] })
type PasswordValues = z.infer<ReturnType<typeof passwordSchema>>

function PasswordForm({ hasPassword }: { hasPassword: boolean }) {
  const [open, setOpen] = useState(false)
  const change = useChangePassword()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema(hasPassword)),
    defaultValues: { current_password: '', new_password: '', confirm: '' },
  })

  const close = () => {
    setOpen(false)
    reset()
    change.reset()
  }

  const onSubmit = handleSubmit(async (values) => {
    try {
      await change.mutateAsync({
        current_password: hasPassword ? values.current_password : undefined,
        new_password: values.new_password,
      })
      toast.success(hasPassword ? 'Password changed. Other devices were signed out.' : 'Password added')
      close()
    } catch {
      // Shown in the form.
    }
  })

  return (
    <div className="flex flex-col">
      <SettingRow
        label="Password"
        hint={
          hasPassword
            ? 'Changing it signs you out on every other device.'
            : 'You sign in with Google, LinkedIn or GitHub. Add a password to sign in with your email too.'
        }
      >
        {!open && (
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            {hasPassword ? 'Change password' : 'Add password'}
          </Button>
        )}
      </SettingRow>
      {open && (
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4 pb-4">
          <FormError message={change.error ? serverMessage(change.error) : null} />
          <div className="grid gap-4 sm:grid-cols-3">
            {hasPassword && (
              <FormField
                label="Current password"
                type="password"
                autoComplete="current-password"
                registration={register('current_password')}
                error={errors.current_password}
              />
            )}
            <FormField
              label="New password"
              type="password"
              autoComplete="new-password"
              registration={register('new_password')}
              error={errors.new_password}
            />
            <FormField
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              registration={register('confirm')}
              error={errors.confirm}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
            <SubmitButton pending={isSubmitting} pendingText="Saving…">
              {hasPassword ? 'Change password' : 'Add password'}
            </SubmitButton>
          </div>
        </form>
      )}
    </div>
  )
}

function ConnectedAccounts({ user }: { user: User }) {
  const disconnect = useDisconnectProvider()
  // Only a connected account can be the last way in here; a lone password is changed above.
  const onlyOne = signInMethodCount(user) <= 1
  const lastIsProvider = onlyOne && !user.has_password

  return (
    <div className="flex flex-col gap-3 py-4">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium">Connected accounts</span>
        <span className="text-sm text-muted-foreground">Sign in with any of these instead of a password.</span>
      </div>
      <FormError message={disconnect.error ? serverMessage(disconnect.error) : null} />
      <ul className="flex flex-col divide-y rounded-lg border">
        {PROVIDERS.map(({ id, label, Icon, iconClass }) => {
          const connected = isConnected(user, id)
          const detail = id === 'github' && user.github_username ? `@${user.github_username}` : null
          return (
            <li key={id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
              <Icon className={`size-5 shrink-0 ${iconClass}`} aria-hidden />
              <span className="flex min-w-0 flex-1 items-center gap-2 text-sm">
                <span className="font-medium">{label}</span>
                {detail && <span className="truncate text-muted-foreground">{detail}</span>}
                {connected && <Badge variant="success">Connected</Badge>}
              </span>
              {connected ? (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Disconnect ${label}`}
                  disabled={onlyOne || disconnect.isPending}
                  title={onlyOne ? 'Add a password or another account first' : undefined}
                  onClick={() =>
                    disconnect.mutate(id, { onSuccess: () => toast.success(`${label} disconnected`) })
                  }
                >
                  Disconnect
                </Button>
              ) : (
                <Button variant="outline" size="sm" asChild>
                  <a href={connectUrl(id)} aria-label={`Connect ${label}`}>
                    Connect
                  </a>
                </Button>
              )}
            </li>
          )
        })}
      </ul>
      {lastIsProvider && (
        <p className="text-xs text-muted-foreground">
          This is your only way to sign in, so it can’t be disconnected. Add a password or connect another account first.
        </p>
      )}
    </div>
  )
}

function SignOutEverywhere() {
  const signOut = useSignOutEverywhere()
  const navigate = useNavigate()

  return (
    <SettingRow
      label="Sign out of all devices"
      hint="Ends every session, including this one. Use it if you signed in on a shared computer or lost a device."
    >
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="outline" size="sm">
            <LogOut />
            Sign out everywhere
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out of all devices?</AlertDialogTitle>
            <AlertDialogDescription>
              You’ll be signed out here and everywhere else, and will need to sign in again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {signOut.error && <FormError message={serverMessage(signOut.error)} />}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault()
                signOut.mutate(undefined, { onSuccess: () => navigate('/login', { replace: true }) })
              }}
              disabled={signOut.isPending}
            >
              Sign out everywhere
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingRow>
  )
}
