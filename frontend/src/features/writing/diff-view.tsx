import { cn } from '@/lib/utils'

import { diffWords } from './diff'
import { PlaceholderText } from './placeholder-text'
import type { Suggestion } from './types'

function TextDiff({ before, after }: { before: string; after: string }) {
  if (!before.trim()) {
    return (
      <p className="rounded-md bg-success-muted p-2 text-sm">
        <span className="sr-only">Added: </span>
        <PlaceholderText text={after} />
      </p>
    )
  }
  return (
    <p className="rounded-md bg-muted/60 p-2 text-sm leading-relaxed">
      {diffWords(before, after).map((part, i) =>
        part.type === 'same' ? (
          <span key={i}>{part.text}</span>
        ) : part.type === 'removed' ? (
          <del key={i} className="rounded bg-danger-muted text-danger-text line-through decoration-destructive/60">
            <span className="sr-only">removed: </span>
            {part.text}
          </del>
        ) : (
          <ins key={i} className="rounded bg-success-muted text-success-text no-underline">
            <span className="sr-only">added: </span>
            <PlaceholderText text={part.text} />
          </ins>
        ),
      )}
    </p>
  )
}

function ListDiff({ before, after, moved }: { before: string[]; after: string[]; moved?: string }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {[
        { title: 'Now', items: before },
        { title: 'Suggested', items: after },
      ].map(({ title, items }) => (
        <div key={title} className="rounded-md bg-muted/60 p-2">
          <p className="mb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{title}</p>
          <ol className="list-decimal pl-5 text-sm">
            {items.map((item, i) => (
              <li
                key={`${item}-${i}`}
                className={cn(title === 'Suggested' && moved && item === moved && 'font-medium text-success-text')}
              >
                {item}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}

export function SuggestionDiff({ suggestion: s }: { suggestion: Suggestion }) {
  if (s.kind === 'rewrite_bullet' || s.kind === 'rewrite_summary') {
    return <TextDiff before={s.before ?? ''} after={s.after ?? ''} />
  }
  if (s.kind === 'add_skill') {
    return (
      <p className="inline-flex self-start rounded-full bg-success-muted px-2.5 py-1 text-sm font-medium text-success-text">
        <span className="sr-only">Add skill: </span>+ {s.after}
      </p>
    )
  }
  return (
    <ListDiff
      before={s.before_items ?? []}
      after={s.after_items ?? []}
      moved={s.kind === 'move_bullet_up' ? s.after_items?.[0] : undefined}
    />
  )
}
