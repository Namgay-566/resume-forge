import { Check, X } from 'lucide-react'

import type { KeywordReport } from './types'

const SOURCE_TEXT: Record<string, string> = {
  ai: 'Keywords extracted from the job description.',
  catalog: 'AI was unavailable, so keywords come from known skills mentioned in the job description.',
  target_role: 'Compared against the skills your target role requires.',
}

export function KeywordChips({ keywords }: { keywords: KeywordReport }) {
  if (!keywords.source) {
    return (
      <p className="text-sm text-muted-foreground">
        Paste a job description or choose a target role to compare keywords.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{SOURCE_TEXT[keywords.extraction ?? 'ai']}</p>
      <ChipGroup title={`Matched (${keywords.matched.length})`} empty="None yet.">
        {keywords.matched.map((hit) => (
          <li
            key={hit.keyword}
            title={hit.matched_as ? `Found as “${hit.matched_as}”` : undefined}
            className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success-muted text-success-text px-2.5 py-1 text-xs font-medium"
          >
            <Check className="size-3.5 text-success-text" aria-hidden />
            {hit.keyword}
            {hit.matched_as && <span className="font-normal text-muted-foreground">({hit.matched_as})</span>}
          </li>
        ))}
      </ChipGroup>
      <ChipGroup title={`Missing (${keywords.missing.length})`} empty="Nothing missing.">
        {keywords.missing.map((hit) => (
          <li
            key={hit.keyword}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-danger/30 px-2.5 py-1 text-xs font-medium"
          >
            <X className="size-3.5 text-danger-text" aria-hidden />
            {hit.keyword}
            {hit.importance === 'preferred' && (
              <span className="font-normal text-muted-foreground">(preferred)</span>
            )}
          </li>
        ))}
      </ChipGroup>
    </div>
  )
}

function ChipGroup({ title, empty, children }: { title: string; empty: string; children: React.ReactNode[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h4>
      {children.length ? <ul className="flex flex-wrap gap-1.5">{children}</ul> : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  )
}
