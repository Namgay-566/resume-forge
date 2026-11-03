import { ArrowRight, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { locationSection, type Fix, type Location } from './types'

const SEVERITY: Record<Fix['severity'], { label: string; className: string }> = {
  high: { label: 'High', className: 'border-danger/30 text-danger-text' },
  medium: { label: 'Medium', className: 'border-warning/50 text-warning-text' },
  low: { label: 'Low', className: 'border-border text-muted-foreground' },
}

function locationLabel(location: Location) {
  const section = locationSection(location)
  return location.item_index === null ? section : `${section} #${location.item_index + 1}`
}

export function FixList({ fixes, onJump }: { fixes: Fix[]; onJump: (location: Location) => void }) {
  if (fixes.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing to fix. Nice work.</p>
  }
  return (
    <ol className="flex flex-col gap-2">
      {fixes.map((fix) => {
        const severity = SEVERITY[fix.severity]
        return (
          <li key={fix.priority} className="flex gap-3 rounded-lg border bg-background p-3">
            <span className="mt-0.5 text-xs font-semibold text-muted-foreground tabular-nums">
              {fix.priority}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className={cn('rounded border px-1.5 text-[11px] font-medium', severity.className)}>
                  {severity.label}
                </span>
                {fix.source === 'ai' && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                    <Sparkles className="size-3" aria-hidden /> Recruiter tip
                  </span>
                )}
                {fix.points !== null && fix.points > 0 && (
                  <span className="text-[11px] text-muted-foreground">up to +{Math.round(fix.points)} pts</span>
                )}
              </div>
              <p className="text-sm font-medium">{fix.title}</p>
              <p className="text-sm text-muted-foreground">{fix.detail}</p>
              {fix.location && (
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto self-start p-0"
                  onClick={() => onJump(fix.location!)}
                >
                  Go to {locationLabel(fix.location)}
                  <ArrowRight />
                </Button>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
