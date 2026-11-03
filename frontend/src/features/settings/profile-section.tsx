import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { FormField } from '@/components/form-field'
import { SubmitButton } from '@/components/submit-button'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import type { User } from '@/features/auth/types'

import { useUpdateProfile } from './api'
import { EmailChange } from './email-change'
import { SettingsSection } from './settings-section'

// Mirrors ProfileUpdate in backend/app/schemas/account.py.
const profileSchema = z.object({
  name: z.string().trim().min(1, 'Enter your name').max(200),
  linkedin_url: z
    .string()
    .trim()
    .max(200)
    .refine(
      (url) => url === '' || /^(https?:\/\/)?(www\.)?linkedin\.com\/.+/i.test(url),
      'Enter a LinkedIn profile link, like linkedin.com/in/your-name',
    ),
})
type ProfileValues = z.infer<typeof profileSchema>

export function ProfileSection({ user }: { user: User }) {
  const update = useUpdateProfile()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    values: { name: user.name, linkedin_url: user.linkedin_url ?? '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    try {
      const updated = await update.mutateAsync({
        name: values.name,
        linkedin_url: values.linkedin_url || null,
      })
      reset({ name: updated.name, linkedin_url: updated.linkedin_url ?? '' })
      toast.success('Profile saved')
    } catch {
      // Shown below the form.
    }
  })

  return (
    <SettingsSection
      id="profile"
      title="Profile"
      description="Your name and links start every new resume. Changing them here doesn’t change resumes you’ve already made."
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4 py-4">
        <FormError message={update.error ? apiErrorMessage(update.error, {}, { useServerDetail: true }) : null} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Full name" autoComplete="name" registration={register('name')} error={errors.name} />
          <FormField
            label="LinkedIn profile (optional)"
            placeholder="linkedin.com/in/your-name"
            inputMode="url"
            registration={register('linkedin_url')}
            error={errors.linkedin_url}
          />
        </div>
        <div className="flex justify-end">
          <SubmitButton pending={isSubmitting} pendingText="Saving…" disabled={!isDirty}>
            Save profile
          </SubmitButton>
        </div>
      </form>
      <EmailChange user={user} />
    </SettingsSection>
  )
}
