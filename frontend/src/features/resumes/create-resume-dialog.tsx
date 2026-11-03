import { zodResolver } from '@hookform/resolvers/zod'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
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
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useAuth } from '@/features/auth/use-auth'
import { useTargetRoles } from '@/features/target-roles/api'
import { RolePicker } from '@/features/target-roles/role-picker'

import { useCreateResume } from './api'
import { ExperienceLevelSelect } from './experience-level'

const createSchema = z.object({
  title: z.string().trim().min(1, 'Give it a name').max(200),
  type: z.enum(['resume', 'cv']),
  target_role_id: z.string().min(1, 'Choose the role you are aiming for'),
  experience_level: z.enum(['student', 'entry', 'mid', 'senior', 'career_changer']).nullable(),
})
type CreateValues = z.infer<typeof createSchema>

const TYPE_OPTIONS = [
  {
    value: 'resume',
    label: 'Resume',
    description: '1–2 pages focused on one target role. Best for most job applications.',
  },
  {
    value: 'cv',
    label: 'CV',
    description: 'Full academic and work history. Common for research, academia and many countries outside the US.',
  },
] as const

export function CreateResumeDialog({ trigger, defaultOpen = false }: { trigger?: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const [serverError, setServerError] = useState<string | null>(null)
  const navigate = useNavigate()
  const roles = useTargetRoles()
  const create = useCreateResume()
  // Start from the defaults in Settings; the template is filled in by the server the same way.
  const prefs = useAuth().user?.preferences

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      title: 'My resume',
      type: prefs?.default_resume_type ?? 'resume',
      target_role_id: '',
      experience_level: prefs?.default_experience_level ?? null,
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      const resume = await create.mutateAsync(values)
      setOpen(false)
      navigate(`/resumes/${resume.id}`)
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          reset()
          setServerError(null)
        }
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <Plus />
            New resume
          </Button>
        )}
      </DialogTrigger>
      <DialogContent
        className="sm:max-w-lg"
        onEscapeKeyDown={(event) => {
          // Escape in the open role list closes the list, not the whole dialog.
          if ((event.target as HTMLElement | null)?.closest?.('[data-picker-open="true"]')) event.preventDefault()
        }}
      >
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <DialogHeader>
            <DialogTitle>New resume</DialogTitle>
            <DialogDescription>
              Your target role and career stage shape the skill gap report, score and advice.
            </DialogDescription>
          </DialogHeader>

          <FormError message={serverError} />
          <FormField label="Name" registration={register('title')} error={errors.title} />

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">Document type</legend>
            <Controller
              control={control}
              name="type"
              render={({ field }) => (
                <RadioGroup value={field.value} onValueChange={field.onChange} className="gap-2">
                  {TYPE_OPTIONS.map((option) => (
                    <Label
                      key={option.value}
                      htmlFor={`type-${option.value}`}
                      className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5"
                    >
                      <RadioGroupItem id={`type-${option.value}`} value={option.value} className="mt-0.5" />
                      <span className="flex flex-col gap-0.5">
                        <span className="font-medium">{option.label}</span>
                        <span className="text-sm text-muted-foreground">{option.description}</span>
                      </span>
                    </Label>
                  ))}
                </RadioGroup>
              )}
            />
          </fieldset>

          <div className="flex flex-col gap-2">
            <Label htmlFor="target-role">Target role</Label>
            <Controller
              control={control}
              name="target_role_id"
              render={({ field }) => (
                <RolePicker
                  id="target-role"
                  inline
                  value={field.value || null}
                  onChange={field.onChange}
                  invalid={Boolean(errors.target_role_id)}
                />
              )}
            />
            {errors.target_role_id && (
              <p className="text-sm text-danger-text">{errors.target_role_id.message}</p>
            )}
            {roles.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No roles yet. Run <code>python -m app.db.seed</code> in the backend.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="experience-level">Career stage</Label>
            <Controller
              control={control}
              name="experience_level"
              render={({ field }) => (
                <ExperienceLevelSelect id="experience-level" value={field.value} onChange={field.onChange} />
              )}
            />
            <p className="text-xs text-muted-foreground">
              Students and career changers are scored on what they have: studies, projects, volunteering and transferable skills.
            </p>
          </div>

          <DialogFooter>
            <SubmitButton pending={isSubmitting} pendingText="Creating…">
              Create and open
            </SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
