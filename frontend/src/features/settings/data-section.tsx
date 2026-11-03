import { zodResolver } from '@hookform/resolvers/zod'
import { Download, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormField } from '@/components/form-field'
import { SubmitButton } from '@/components/submit-button'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import type { User } from '@/features/auth/types'

import { useDeleteAccount, useExportData } from './api'
import { SettingRow, SettingsSection } from './settings-section'

export function DataSection() {
  const exportData = useExportData()

  return (
    <SettingsSection id="data" title="Your data" description="Everything you’ve added to ResumeForge belongs to you.">
      <SettingRow
        label="Download your data"
        hint="A ZIP with your resumes, scores, skills, roadmap, proofs and the files you uploaded."
      >
        <Button
          variant="outline"
          size="sm"
          disabled={exportData.isPending}
          aria-busy={exportData.isPending || undefined}
          onClick={() =>
            exportData.mutate(undefined, {
              onError: (error) => toast.error(apiErrorMessage(error, {}, { useServerDetail: true })),
            })
          }
        >
          <Download />
          {exportData.isPending ? 'Preparing…' : 'Download'}
        </Button>
      </SettingRow>
    </SettingsSection>
  )
}

export function DangerZone({ user }: { user: User }) {
  return (
    <SettingsSection id="delete" title="Danger zone" danger>
      <SettingRow
        label="Delete account"
        hint="Permanently deletes your account, resumes, proofs, uploaded files and roadmap. This can’t be undone."
      >
        <DeleteAccountDialog user={user} />
      </SettingRow>
    </SettingsSection>
  )
}

const deleteSchema = (email: string, hasPassword: boolean) =>
  z.object({
    confirm_email: z
      .string()
      .trim()
      .refine((value) => value.toLowerCase() === email.toLowerCase(), 'Type your email address exactly as shown'),
    current_password: hasPassword ? z.string().min(1, 'Enter your password') : z.string(),
  })
type DeleteValues = z.infer<ReturnType<typeof deleteSchema>>

function DeleteAccountDialog({ user }: { user: User }) {
  const [open, setOpen] = useState(false)
  const remove = useDeleteAccount()
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<DeleteValues>({
    resolver: zodResolver(deleteSchema(user.email, user.has_password)),
    defaultValues: { confirm_email: '', current_password: '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    try {
      await remove.mutateAsync({
        confirm_email: values.confirm_email,
        current_password: user.has_password ? values.current_password : undefined,
      })
      toast.success('Your account was deleted')
      navigate('/', { replace: true })
    } catch {
      // Shown in the dialog.
    }
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          reset()
          remove.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm">
          <Trash2 />
          Delete account
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <DialogHeader>
            <DialogTitle>Delete your account?</DialogTitle>
            <DialogDescription>
              Everything goes: your resumes, ATS scores, skills, roadmap, proofs and uploaded files. Download your data
              first if you want a copy.
            </DialogDescription>
          </DialogHeader>
          <FormError message={remove.error ? apiErrorMessage(remove.error, {}, { useServerDetail: true }) : null} />
          <FormField
            label={`Type ${user.email} to confirm`}
            autoComplete="off"
            spellCheck={false}
            registration={register('confirm_email')}
            error={errors.confirm_email}
          />
          {user.has_password && (
            <FormField
              label="Password"
              type="password"
              autoComplete="current-password"
              registration={register('current_password')}
              error={errors.current_password}
            />
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Keep my account
            </Button>
            <SubmitButton variant="destructive" pending={isSubmitting} pendingText="Deleting…">
              Delete forever
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
