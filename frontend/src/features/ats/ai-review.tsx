import { AlertTriangle, CheckCircle2, CircleDot, Info } from 'lucide-react'

import { SECTION_LABELS, type AtsReport } from './types'

const RATING = {
  strong: { label: 'Strong', icon: CheckCircle2, className: 'text-success-text' },
  ok: { label: 'OK', icon: CircleDot, className: 'text-muted-foreground' },
  weak: { label: 'Weak', icon: AlertTriangle, className: 'text-warning-text' },
} as const

export function AIReviewPanel({ report }: { report: AtsReport }) {
  if (!report.ai_review) {
    return (
      <p className="flex gap-2 rounded-lg bg-muted/60 p-3 text-sm text-muted-foreground">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        {report.ai_status === 'unavailable'
          ? 'The recruiter review needs the AI service, which isn’t available right now. Your score above was calculated without it.'
          : report.ai_status === 'skipped'
            ? 'This was a quick re-score without the recruiter review. Run “Check again” for a full review.'
            : report.ai_status === 'rate_limited'
              ? 'You’ve used your AI requests for now, so this check skipped the recruiter review. Your score is unaffected.'
              : 'The recruiter review couldn’t be generated this time. Your score above is unaffected; try again later.'}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">{report.ai_review.overall}</p>
      {report.ai_review.sections.map((section) => {
        const rating = RATING[section.rating]
        const Icon = rating.icon
        return (
          <details key={section.section} className="group rounded-lg border bg-background p-3">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-sm font-medium">
              {SECTION_LABELS[section.section]}
              <span className={`inline-flex items-center gap-1 text-xs ${rating.className}`}>
                <Icon className="size-3.5" aria-hidden />
                {rating.label}
              </span>
            </summary>
            <p className="mt-2 text-sm text-muted-foreground">{section.feedback}</p>
            {section.suggestions.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-sm">
                {section.suggestions.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
          </details>
        )
      })}
    </div>
  )
}
