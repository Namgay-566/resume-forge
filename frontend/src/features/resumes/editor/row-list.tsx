import { Plus } from 'lucide-react'
import { get, useFieldArray, useFormContext, useFormState, useWatch, type FieldError } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { BulletImprove } from '@/features/writing/bullet-improve'
import { findPlaceholders } from '@/features/writing/diff'

import { emptyItem, LIMITS, type ResumeFormValues } from '../form-schema'
import { itemAnchor } from './anchors'
import { ItemControls } from './section-card'

export type RowListName =
  | `data.${'experience' | 'education' | 'projects'}.${number}.bullets`
  | `data.sections.${number}.entries.${number}.bullets`
  | 'data.achievements'

interface RowListProps {
  name: RowListName
  label: string
  itemLabel: string
  addLabel: string
  placeholder?: string
  /** Which entry these rows belong to, so labels are unique ("Position 2, highlight 1"). */
  context?: string
}

/** Reorderable list of one-line entries (bullet points, achievements). */
/** Reminds the user to replace AI placeholders like [X%] with a real figure. */
function PlaceholderHint({ name }: { name: string }) {
  const value = useWatch<ResumeFormValues>({ name: name as 'data.summary' }) as string | undefined
  const found = findPlaceholders(value ?? '')
  if (found.length === 0) return null
  return <p className="text-xs text-warning-text">Replace {found.join(', ')} with your real number.</p>
}

export function RowList({ name, label, itemLabel, addLabel, placeholder, context }: RowListProps) {
  // Every bullet list gets AI "Improve", worded for its section.
  const { control, register } = useFormContext<ResumeFormValues>()
  const { errors } = useFormState<ResumeFormValues>({ name })
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: name as 'data.achievements',
  })
  const max = name === 'data.achievements' ? LIMITS.entries : LIMITS.bullets
  const full = fields.length >= max

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1.5 text-sm font-medium">{label}</legend>
      {fields.length === 0 && <p className="text-sm text-muted-foreground">None yet.</p>}
      <ul className="flex flex-col gap-2">
        {fields.map((field, index) => {
          const inputName = `${name}.${index}.value` as const
          const error = get(errors, inputName) as FieldError | undefined
          const rowLabel = context ? `${context}, ${itemLabel.toLowerCase()} ${index + 1}` : `${itemLabel} ${index + 1}`
          return (
            <li
              key={field.id}
              id={name === 'data.achievements' ? itemAnchor('achievements', index) : undefined}
              className="flex flex-col gap-1"
            >
              <div className="flex items-center gap-1">
                <Label htmlFor={inputName} className="sr-only">
                  {rowLabel}
                </Label>
                <Input
                  id={inputName}
                  placeholder={placeholder}
                  aria-invalid={error ? true : undefined}
                  {...register(inputName as 'data.achievements.0.value')}
                />
                <BulletImprove name={name} bulletIndex={index} label={rowLabel} />
                <ItemControls
                  index={index}
                  total={fields.length}
                  label={rowLabel}
                  onMove={move}
                  onRemove={remove}
                />
              </div>
              {error ? (
                <p className="text-xs text-danger-text">{error.message}</p>
              ) : (
                <PlaceholderHint name={inputName} />
              )}
            </li>
          )
        })}
      </ul>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="self-start"
        disabled={full}
        onClick={() => append(emptyItem.row())}
      >
        <Plus />
        {full ? `Up to ${max}` : addLabel}
      </Button>
    </fieldset>
  )
}
