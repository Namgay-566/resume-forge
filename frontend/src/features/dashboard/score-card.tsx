import { ArrowRight, Minus, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { ProgressRing } from '@/components/progress-ring'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

import type { Band } from './status'

interface ScoreCardProps {
  title: string
  icon: LucideIcon
  value: number | null
  /** Arc color; the history chart uses the same one for this score. */
  color: string
  band: Band | null
  delta: number | null
  context: ReactNode
  action: { label: string; to: string }
  /** Shown instead of the band when there's no value yet. */
  emptyHint: string
  /** Under the number in the ring. */
  unit: string
}

export function ScoreCard({ title, icon: Icon, value, color, band, delta, context, action, emptyHint, unit }: ScoreCardProps) {
  return (
    <Card className="gap-5 px-5 py-5 sm:px-6">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Icon className="size-4" style={{ color }} aria-hidden />
        {title}
      </div>
      <div className="flex items-center gap-5">
        <ProgressRing value={value} color={color} label={title} size={128} stroke={11} caption={value === null ? undefined : unit} />
        <div className="flex min-w-0 flex-col items-start gap-2">
          {value === null ? (
            <p className="text-sm text-muted-foreground">{emptyHint}</p>
          ) : (
            <>
              {band && <Badge variant={band.tone}>{band.label}</Badge>}
              <DeltaLine delta={delta} />
            </>
          )}
          <p className="text-xs text-muted-foreground">{context}</p>
        </div>
      </div>
      <Button asChild variant={value === null ? 'default' : 'outline'} size="sm" className="mt-auto self-start">
        <Link to={action.to}>
          {action.label} <ArrowRight />
        </Link>
      </Button>
    </Card>
  )
}

function DeltaLine({ delta }: { delta: number | null }) {
  if (delta === null) return <p className="text-xs text-muted-foreground">First measurement</p>
  const Icon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus
  const tone = delta > 0 ? 'text-success-text' : delta < 0 ? 'text-danger-text' : 'text-muted-foreground'
  return (
    <p className={`flex items-center gap-1 text-sm font-medium ${tone}`}>
      <Icon className="size-4" aria-hidden />
      {delta > 0 ? `+${delta}` : delta === 0 ? 'No change' : delta} {delta !== 0 && <span className="font-normal text-muted-foreground">since last check</span>}
    </p>
  )
}

export function ScoreCardSkeleton() {
  return (
    <Card className="gap-5 px-5 py-5 sm:px-6" aria-hidden>
      <Skeleton className="h-4 w-28" />
      <div className="flex items-center gap-5">
        <Skeleton className="size-32 rounded-full" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
      <Skeleton className="h-8 w-32 rounded-md" />
    </Card>
  )
}
