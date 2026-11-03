import type { ComponentProps, ReactNode } from 'react'
import { Controller, get, useFormContext, useFormState, type FieldError, type Path } from 'react-hook-form'

import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

import type { ResumeFormValues } from '../form-schema'

type Name = Path<ResumeFormValues>

function useFieldError(name: Name): FieldError | undefined {
  const { errors } = useFormState<ResumeFormValues>({ name })
  return get(errors, name) as FieldError | undefined
}

interface FieldShellProps {
  id: string
  label: string
  hint?: string
  error?: FieldError
  className?: string
  children: ReactNode
}

function FieldShell({ id, label, hint, error, className, children }: FieldShellProps) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-danger-text">
          {error.message}
        </p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}

interface TextFieldProps extends Omit<ComponentProps<typeof Input>, 'name' | 'id'> {
  name: Name
  label: string
  hint?: string
}

export function TextField({ name, label, hint, className, ...props }: TextFieldProps) {
  const { register } = useFormContext<ResumeFormValues>()
  const error = useFieldError(name)
  return (
    <FieldShell id={name} label={label} hint={hint} error={error} className={className}>
      <Input
        id={name}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${name}-error` : undefined}
        {...props}
        {...register(name)}
      />
    </FieldShell>
  )
}

interface TextAreaFieldProps extends Omit<ComponentProps<typeof Textarea>, 'name' | 'id'> {
  name: Name
  label: string
  hint?: string
}

export function TextAreaField({ name, label, hint, className, ...props }: TextAreaFieldProps) {
  const { register } = useFormContext<ResumeFormValues>()
  const error = useFieldError(name)
  return (
    <FieldShell id={name} label={label} hint={hint} error={error} className={className}>
      <Textarea
        id={name}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${name}-error` : undefined}
        {...props}
        {...register(name)}
      />
    </FieldShell>
  )
}

/** Month picker where supported; falls back to a YYYY-MM text box elsewhere. */
export function MonthField(props: Omit<TextFieldProps, 'type'>) {
  return <TextField type="month" placeholder="YYYY-MM" {...props} />
}

interface CheckboxFieldProps {
  name: Name
  label: string
  onCheckedChange?: (checked: boolean) => void
}

export function CheckboxField({ name, label, onCheckedChange }: CheckboxFieldProps) {
  const { control } = useFormContext<ResumeFormValues>()
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <div className="flex items-center gap-2">
          <Checkbox
            id={name}
            checked={field.value === true}
            onCheckedChange={(checked) => {
              field.onChange(checked === true)
              onCheckedChange?.(checked === true)
            }}
            onBlur={field.onBlur}
          />
          <Label htmlFor={name} className="font-normal">
            {label}
          </Label>
        </div>
      )}
    />
  )
}
