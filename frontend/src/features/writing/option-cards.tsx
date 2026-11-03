import { Check } from 'lucide-react'
import { useEffect, useRef, type KeyboardEvent } from 'react'

import { cn } from '@/lib/utils'

import { diffWords } from './diff'
import { PlaceholderNote, PlaceholderText } from './placeholder-text'
import type { WritingOption } from './types'

interface OptionCardsProps {
  original: string
  options: WritingOption[]
  selected: number
  onSelect: (index: number) => void
  /** Enter on a card accepts it. */
  onAccept: () => void
  label: string
}

/** AI suggestions as a radio group of cards, each showing what changed from the original.
 * Arrow keys move the selection (roving focus), Enter accepts. */
export function OptionCards({ original, options, selected, onSelect, onAccept, label }: OptionCardsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  // When the options arrive, put keyboard focus on the selected one.
  useEffect(() => {
    refs.current[selected]?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount
  }, [])

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const last = options.length - 1
    const next =
      event.key === 'ArrowDown' || event.key === 'ArrowRight'
        ? index === last ? 0 : index + 1
        : event.key === 'ArrowUp' || event.key === 'ArrowLeft'
          ? index === 0 ? last : index - 1
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : null
    if (next !== null) {
      event.preventDefault()
      onSelect(next)
      refs.current[next]?.focus()
    } else if (event.key === 'Enter') {
      event.preventDefault()
      onAccept()
    }
  }

  return (
    <div role="radiogroup" aria-label={label} className="flex flex-col gap-2">
      {options.map((option, i) => {
        const isSelected = i === selected
        return (
          <button
            key={i}
            ref={(el) => {
              refs.current[i] = el
            }}
            type="button"
            role="radio"
            aria-checked={isSelected}
            tabIndex={isSelected ? 0 : -1}
            onClick={() => onSelect(i)}
            onDoubleClick={onAccept}
            onKeyDown={(event) => onKeyDown(event, i)}
            className={cn(
              'group relative flex flex-col gap-2 rounded-xl border-2 bg-card p-3 pr-10 text-left transition-[border-color,background-color,box-shadow] outline-none focus-visible:ring-3 focus-visible:ring-ring/40',
              isSelected ? 'border-primary bg-secondary/60 shadow-sm' : 'border-border hover:border-primary/40 hover:bg-muted/50',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'absolute top-3 right-3 flex size-5 items-center justify-center rounded-full border-2 transition-colors',
                isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/40',
              )}
            >
              {isSelected && <Check className="size-3" strokeWidth={3} />}
            </span>
            <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Option {i + 1}</span>
            <span className="text-sm leading-relaxed">
              <Diff before={original} after={option.text} />
            </span>
            {option.rationale && <span className="text-xs text-muted-foreground">{option.rationale}</span>}
            <PlaceholderNote placeholders={option.placeholders} replaced={option.replaced_numbers} />
          </button>
        )
      })}
    </div>
  )
}

/** Word-level changes: additions highlighted, removals shown struck through. */
function Diff({ before, after }: { before: string; after: string }) {
  if (!before.trim()) return <PlaceholderText text={after} />
  const parts = diffWords(before, after)
  // A near-total rewrite reads better as clean text: your original is shown above anyway.
  const kept = parts.filter((p) => p.type === 'same').reduce((n, p) => n + p.text.trim().split(/\s+/).filter(Boolean).length, 0)
  const originalWords = before.trim().split(/\s+/).length
  if (kept / originalWords < 0.4) return <PlaceholderText text={after} />
  return (
    <>
      {parts.map((part, i) =>
        part.type === 'same' ? (
          <span key={i}>{part.text}</span>
        ) : part.type === 'removed' ? (
          <del key={i} className="text-muted-foreground line-through decoration-danger/60">
            <span className="sr-only">removed: </span>
            {part.text}
          </del>
        ) : (
          <ins key={i} className="rounded-sm bg-success-muted px-0.5 text-success-text no-underline">
            <span className="sr-only">added: </span>
            <PlaceholderText text={part.text} />
          </ins>
        ),
      )}
    </>
  )
}
