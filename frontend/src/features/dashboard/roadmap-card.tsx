import { ArrowRight, Clock, Map as MapIcon, Target } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardSummary } from '@/features/roadmap/types'

const PLAN_LABEL = { not_started: 'Not started', in_progress: 'In progress', done: 'Done' } as const

export function RoadmapCard({ data }: { data: DashboardSummary }) {
  const totals = data.totals
  if (!totals || !data.role) {
    return (
      <Card className="justify-center px-5 py-5 sm:px-6">
        <EmptyState
          size="sm"
          icon={Target}
          title="No roadmap yet"
          description="Choose a target role on a resume to get a step-by-step plan."
          actions={
            data.resume_id && (
              <Button asChild size="sm">
                <Link to={`/resumes/${data.resume_id}`}>Choose a role</Link>
              </Button>
            )
          }
        />
      </Card>
    )
  }
  const percent = totals.items ? Math.round((totals.done / totals.items) * 100) : 0
  return (
    <Card className="gap-5 px-5 py-5 sm:px-6">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <MapIcon className="size-4 text-primary" aria-hidden /> Roadmap progress
      </div>
      <div className="flex items-end justify-between gap-3">
        <p className="font-heading text-4xl leading-none font-semibold tracking-tight tabular-nums">
          {totals.done}
          <span className="text-lg font-normal text-muted-foreground"> / {totals.items}</span>
        </p>
        <p className="text-sm font-medium text-muted-foreground tabular-nums">{percent}% done</p>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-label="Roadmap items done"
        aria-valuemin={0}
        aria-valuemax={totals.items}
        aria-valuenow={totals.done}
        aria-valuetext={`${totals.done} of ${totals.items} done`}
      >
        <div className="h-full rounded-full bg-gradient-to-r from-primary to-highlight transition-[width] duration-700 ease-out-soft" style={{ width: `${Math.max(percent, totals.done ? 4 : 0)}%` }} />
      </div>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{totals.in_progress} in progress</span>
        <span className="flex items-center gap-1">
          <Clock className="size-3.5" aria-hidden /> about {totals.hours_remaining} h left
        </span>
        <span className="truncate">for {data.role.name}</span>
      </p>
      {data.next_up && (
        <Link
          to={`/roadmap?resume=${data.resume_id}#roadmap-${data.next_up.slug}`}
          className="group flex items-center justify-between gap-3 rounded-xl border bg-muted/50 px-3.5 py-3 transition-colors hover:bg-muted"
        >
          <span className="min-w-0">
            <span className="block text-[11px] text-muted-foreground">Up next · {PLAN_LABEL[data.next_up.plan_status]}</span>
            <span className="block truncate text-sm font-medium">{data.next_up.name}</span>
          </span>
          <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      )}
      <Button asChild variant="link" size="sm" className="mt-auto self-start">
        <Link to={`/roadmap?resume=${data.resume_id}`}>
          Open roadmap <ArrowRight />
        </Link>
      </Button>
    </Card>
  )
}

export function RoadmapSkeleton() {
  return (
    <Card className="gap-5 px-5 py-5 sm:px-6" aria-hidden>
      <Skeleton className="h-4 w-32" />
      <div className="flex items-end justify-between">
        <Skeleton className="h-9 w-20" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="h-2.5 w-full rounded-full" />
      <Skeleton className="h-3 w-3/4" />
      <Skeleton className="h-14 w-full rounded-xl" />
    </Card>
  )
}
