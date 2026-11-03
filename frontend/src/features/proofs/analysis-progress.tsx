import { Check, Clock, Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { Proof } from './types'

// Mirrors STAGES in backend/app/services/proofs/pipeline.py: these are the analysis's real
// steps, reported by the backend as it reaches each one.
const STEPS: Record<Proof['type'], { id: string; label: string }[]> = {
  github_repo: [
    { id: 'fetching', label: 'Fetching repo' },
    { id: 'commits', label: 'Checking commits' },
    { id: 'reviewing', label: 'Reviewing code' },
    { id: 'writing', label: 'Writing report' },
  ],
  certificate: [
    { id: 'reading', label: 'Reading certificate' },
    { id: 'matching', label: 'Matching your name' },
    { id: 'checking_link', label: 'Checking the issuer’s site' },
    { id: 'writing', label: 'Writing report' },
  ],
  live_link: [
    { id: 'fetching', label: 'Visiting the site' },
    { id: 'linking', label: 'Linking it to your repo' },
    { id: 'writing', label: 'Writing report' },
  ],
  professional_license: [
    { id: 'reading', label: 'Reading the licence' },
    { id: 'matching', label: 'Matching your name and checking expiry' },
    { id: 'checking_register', label: 'Checking the public register' },
    { id: 'writing', label: 'Writing report' },
  ],
  portfolio_link: [
    { id: 'fetching', label: 'Visiting the page' },
    { id: 'reviewing', label: 'Reviewing the work' },
    { id: 'writing', label: 'Writing report' },
  ],
  work_sample: [
    { id: 'reading', label: 'Reading the file' },
    { id: 'reviewing', label: 'Reviewing the work' },
    { id: 'writing', label: 'Writing report' },
  ],
  publication: [
    { id: 'resolving', label: 'Looking it up' },
    { id: 'matching', label: 'Finding you among the authors' },
    { id: 'reviewing', label: 'Reviewing it' },
    { id: 'writing', label: 'Writing report' },
  ],
  reference_letter: [
    { id: 'reading', label: 'Reading the letter' },
    { id: 'matching', label: 'Matching your name' },
    { id: 'writing', label: 'Writing report' },
  ],
  experience_letter: [
    { id: 'reading', label: 'Reading the letter' },
    { id: 'matching', label: 'Matching your name' },
    { id: 'writing', label: 'Writing report' },
  ],
}

const HEADLINE: Record<Proof['type'], string> = {
  github_repo: 'Analyzing your repo…',
  certificate: 'Checking your certificate…',
  live_link: 'Checking your site…',
  professional_license: 'Checking your licence…',
  portfolio_link: 'Reviewing your portfolio…',
  work_sample: 'Reviewing your work…',
  publication: 'Checking your publication…',
  reference_letter: 'Reading your letter…',
  experience_letter: 'Reading your letter…',
}

interface AnalysisProgressProps {
  proof: Pick<Proof, 'type' | 'status' | 'progress'>
  /** Compact: a single line with dots (for cards). Full: a vertical stepper. */
  compact?: boolean
}

export function AnalysisProgress({ proof, compact = false }: AnalysisProgressProps) {
  const steps = STEPS[proof.type]
  const current = proof.status === 'pending' ? -1 : Math.max(0, steps.findIndex((s) => s.id === proof.progress))
  const now = current === -1 ? 'Queued, starting in a moment' : steps[current].label

  if (compact) {
    return (
      <div className="flex flex-col gap-2" aria-live="polite">
        <p className="flex items-center gap-2 text-sm font-medium text-info-text">
          <Loader2 className="size-4 animate-spin" aria-hidden /> {HEADLINE[proof.type]}
        </p>
        <div className="flex gap-1" aria-hidden>
          {steps.map((s, i) => (
            <span
              key={s.id}
              className={cn(
                'h-1.5 flex-1 rounded-full',
                i < current ? 'bg-info' : i === current ? 'animate-pulse bg-info/60' : 'bg-muted',
              )}
            />
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{now}</p>
      </div>
    )
  }

  return (
    <section aria-labelledby="analysis-heading" className="relative overflow-hidden rounded-2xl border border-info/25 bg-card p-6 shadow-sm">
      {/* A slow sweep across the card while work is happening. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -translate-x-full animate-[rf-sweep_2.4s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-info-muted/70 to-transparent motion-reduce:hidden" />
      <div className="relative flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <span className="relative flex size-11 items-center justify-center rounded-2xl bg-info-muted text-info-text">
            <Loader2 className="size-5 animate-spin" aria-hidden />
          </span>
          <div>
            <h2 id="analysis-heading" className="text-h4">
              {HEADLINE[proof.type]}
            </h2>
            <p className="text-sm text-muted-foreground">Usually under a minute. You can leave this page; we&apos;ll keep going.</p>
          </div>
        </div>
        <ol className="flex flex-col gap-3" aria-live="polite">
          {steps.map((s, i) => {
            const state = i < current ? 'done' : i === current ? 'active' : 'todo'
            return (
              <li key={s.id} className="flex items-center gap-3" aria-current={state === 'active' ? 'step' : undefined}>
                <span
                  className={cn(
                    'flex size-7 shrink-0 items-center justify-center rounded-full border-2 transition-colors',
                    state === 'done' && 'border-success bg-success text-success-foreground',
                    state === 'active' && 'border-info text-info-text',
                    state === 'todo' && 'border-border text-muted-foreground',
                  )}
                >
                  {state === 'done' ? (
                    <Check className="size-3.5" strokeWidth={3} aria-hidden />
                  ) : state === 'active' ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  ) : (
                    <span className="size-1.5 rounded-full bg-current" aria-hidden />
                  )}
                </span>
                <span className={cn('text-sm', state === 'todo' ? 'text-muted-foreground' : 'font-medium')}>
                  {s.label}
                  <span className="sr-only">{state === 'done' ? ' (done)' : state === 'active' ? ' (in progress)' : ''}</span>
                </span>
              </li>
            )
          })}
        </ol>
        {current === -1 && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="size-4" aria-hidden /> Queued, starting in a moment.
          </p>
        )}
      </div>
    </section>
  )
}
