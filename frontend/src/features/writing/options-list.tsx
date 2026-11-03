import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { FormError } from '@/features/auth/form-error'

import { PlaceholderNote, PlaceholderText } from './placeholder-text'
import type { WritingOption } from './types'

interface OptionsListProps {
  pending: boolean
  error: string | null
  options: WritingOption[] | undefined
  onUse: (option: WritingOption) => void
  loadingText: string
}

export function OptionsList({ pending, error, options, onUse, loadingText }: OptionsListProps) {
  if (pending) {
    return (
      <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground" aria-live="polite">
        <Loader2 className="size-4 animate-spin" /> {loadingText}
      </p>
    )
  }
  if (error) return <FormError message={error} />
  if (!options) return null
  if (options.length === 0) {
    return <p className="text-sm text-muted-foreground">No better version found. Try adding more detail first.</p>
  }
  return (
    <ul className="flex flex-col gap-2">
      {options.map((option, i) => (
        <li key={i} className="flex flex-col gap-2 rounded-lg border bg-background p-3">
          <p className="text-sm">
            <PlaceholderText text={option.text} />
          </p>
          {option.rationale && <p className="text-xs text-muted-foreground">{option.rationale}</p>}
          <PlaceholderNote placeholders={option.placeholders} replaced={option.replaced_numbers} />
          <Button type="button" size="sm" variant="outline" className="self-start" onClick={() => onUse(option)}>
            Use this
          </Button>
        </li>
      ))}
    </ul>
  )
}
