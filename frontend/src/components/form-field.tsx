import type { ComponentProps } from 'react'
import type { FieldError, UseFormRegisterReturn } from 'react-hook-form'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface FormFieldProps extends Omit<ComponentProps<typeof Input>, keyof UseFormRegisterReturn> {
  label: string
  registration: UseFormRegisterReturn
  error?: FieldError
}

export function FormField({ label, registration, error, id, ...inputProps }: FormFieldProps) {
  const inputId = id ?? registration.name
  const errorId = `${inputId}-error`
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={inputId}>{label}</Label>
      <Input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...inputProps}
        {...registration}
      />
      {error && (
        <p id={errorId} className="text-sm text-danger-text">
          {error.message}
        </p>
      )}
    </div>
  )
}
