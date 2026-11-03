import { Fragment } from 'react'

/** Text with [X%]-style placeholders highlighted so they can't be missed. */
export function PlaceholderText({ text }: { text: string }) {
  const parts = text.split(/(\[[^[\]\n]{1,24}\])/g)
  return (
    <>
      {parts.map((part, i) =>
        /^\[[^[\]\n]{1,24}\]$/.test(part) ? (
          <mark key={i} className="rounded bg-highlight-muted px-0.5 font-medium text-highlight-text ring-1 ring-highlight/40">
            {part}
          </mark>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  )
}

export function PlaceholderNote({ placeholders, replaced = [] }: { placeholders: string[]; replaced?: string[] }) {
  if (placeholders.length === 0) return null
  return (
    <p className="text-xs text-warning-text">
      Fill in {placeholders.join(', ')} with your real number
      {replaced.length > 0 && ` (the AI suggested ${replaced.join(', ')}, which isn't in your text)`}. If you
      don't know it, remove that part.
    </p>
  )
}
