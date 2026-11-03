import { ArrowRight, Check, Clock } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '@/features/skill-gap/status-badge'
import { cn } from '@/lib/utils'
import { notifyError, notifySuccess } from '@/lib/notify'

import { useSetPlanStatus } from './api'
import type { RoadmapItem } from './types'

const IMPORTANCE = { critical: 'Critical', important: 'Important', nice_to_have: 'Nice to have' } as const

interface RoadmapTimelineProps {
  items: RoadmapItem[]
  resumeId: string
  /** Full: each step's body is `renderBody(item)`. Compact: a one-line summary linking to it. */
  renderBody?: (item: RoadmapItem, step: number) => ReactNode
}

/** Steps on a vertical line. The node is a checkbox: tick a step off when you've done it. */
export function RoadmapTimeline({ items, resumeId, renderBody }: RoadmapTimelineProps) {
  const setStatus = useSetPlanStatus(resumeId)
  return (
    <ol className="relative flex flex-col gap-4">
      <span aria-hidden className="absolute top-5 bottom-5 left-[1.1875rem] w-0.5 rounded-full bg-border" />
      {items.map((item, i) => {
        const done = item.plan_status === 'done'
        const doing = item.plan_status === 'in_progress'
        return (
          <li key={item.skill_id} id={`roadmap-${item.slug}`} className="relative flex scroll-mt-32 gap-4">
            <button
              type="button"
              role="checkbox"
              aria-checked={done}
              aria-label={`Mark ${item.name} as ${done ? 'not done' : 'done'}`}
              onClick={() =>
                setStatus.mutate(
                  { skillId: item.skill_id, status: done ? 'not_started' : 'done' },
                  {
                    onSuccess: () => !done && notifySuccess(`${item.name} marked done`, 'Upload proof to get it verified.'),
                    onError: (err) => notifyError('Couldn’t update your roadmap', err),
                  },
                )
              }
              className={cn(
                'relative z-10 mt-1 flex size-10 shrink-0 items-center justify-center rounded-full border-2 bg-background transition-[background-color,border-color,transform] duration-200 outline-none hover:scale-105 focus-visible:ring-3 focus-visible:ring-ring/40',
                done && 'border-success bg-success text-success-foreground',
                doing && 'border-primary text-primary',
                !done && !doing && 'border-border text-muted-foreground hover:border-primary/50',
              )}
            >
              {done ? (
                <Check className="size-5" strokeWidth={3} aria-hidden />
              ) : (
                <span className="text-sm font-semibold tabular-nums" aria-hidden>
                  {i + 1}
                </span>
              )}
              {doing && <span aria-hidden className="absolute inset-0 animate-ping rounded-full border-2 border-primary/40 motion-reduce:hidden" />}
            </button>
            <div className="min-w-0 flex-1">
              {renderBody ? renderBody(item, i + 1) : <CompactStep item={item} resumeId={resumeId} />}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function CompactStep({ item, resumeId }: { item: RoadmapItem; resumeId: string }) {
  const done = item.plan_status === 'done'
  return (
    <Link
      to={`/roadmap?resume=${resumeId}#roadmap-${item.slug}`}
      className="group flex items-center gap-3 rounded-xl border bg-card px-4 py-3 shadow-xs transition-colors outline-none hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/40"
    >
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className={cn('font-semibold', done && 'text-muted-foreground line-through')}>{item.name}</span>
          {item.plan_status === 'in_progress' && <Badge variant="info">In progress</Badge>}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{IMPORTANCE[item.importance]}</span>
          <span className="flex items-center gap-1">
            <Clock className="size-3" aria-hidden /> ~{item.hours.total} h
          </span>
        </span>
      </span>
      <StatusBadge status={item.gap_status} />
      <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Link>
  )
}
