import { ArrowRight, BadgeCheck, FilePlus2, Gauge, Hammer, Target, Trophy, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { NextAction, NextActionKind } from '@/features/roadmap/types'

import { nextActionHref } from './next-action'

const ACTIONS: Record<NextActionKind, { icon: LucideIcon; cta: string }> = {
  create_resume: { icon: FilePlus2, cta: 'Build my resume' },
  choose_role: { icon: Target, cta: 'Choose a target role' },
  continue_skill: { icon: Hammer, cta: 'Continue' },
  close_gap: { icon: Target, cta: 'Start here' },
  prove_skill: { icon: BadgeCheck, cta: 'Upload proof' },
  run_ats: { icon: Gauge, cta: 'Run ATS check' },
  improve_ats: { icon: Gauge, cta: 'Open ATS check' },
  all_set: { icon: Trophy, cta: 'Open resume' },
}

/** The one thing to do next. Warm accent so it stands apart from every other card. */
export function NextActionCard({ action }: { action: NextAction }) {
  const { icon: Icon, cta } = ACTIONS[action.kind]
  return (
    <section
      aria-labelledby="next-action-heading"
      className="relative isolate flex flex-col gap-5 overflow-hidden rounded-2xl border border-highlight/35 bg-highlight-muted p-5 shadow-sm sm:flex-row sm:items-center sm:p-6"
    >
      <div aria-hidden className="pointer-events-none absolute -top-16 -right-10 -z-10 size-56 rounded-full bg-highlight/20 blur-3xl" />
      <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-highlight text-highlight-foreground shadow-sm">
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="eyebrow text-highlight-text">Next best action</p>
        <h2 id="next-action-heading" className="text-h3 text-foreground">
          {action.title}
        </h2>
        <p className="text-sm text-muted-foreground">{action.detail}</p>
      </div>
      <Button asChild variant="highlight" size="lg" className="w-full shrink-0 sm:w-auto">
        <Link to={nextActionHref(action)}>
          {cta} <ArrowRight />
        </Link>
      </Button>
    </section>
  )
}

export function NextActionSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-5 rounded-2xl border p-5 sm:flex-row sm:items-center sm:p-6">
      <Skeleton className="size-12 rounded-2xl" />
      <div className="flex flex-1 flex-col gap-2">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-6 w-3/5" />
        <Skeleton className="h-4 w-4/5" />
      </div>
      <Skeleton className="h-11 w-full rounded-xl sm:w-36" />
    </div>
  )
}
