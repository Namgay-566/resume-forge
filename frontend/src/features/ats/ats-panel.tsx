import { Gauge, Loader2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { formatRelativeTime } from '@/lib/format'

import { AIReviewPanel } from './ai-review'
import { useLatestAnalysis, useRunAnalysis } from './api'
import { CategoryMeters } from './category-meters'
import { FixList } from './fix-list'
import { KeywordChips } from './keyword-chips'
import { ScoreRing } from './score-ring'
import { Delta } from './score-delta'
import type { Location } from './types'

const MAX_JD = 20_000

interface AtsPanelProps {
  resumeId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Saves pending edits; resolves false if the draft can't be saved yet. */
  saveNow: () => Promise<boolean>
  /** When the resume was last saved, to flag results that are out of date. */
  lastSavedAt: Date | null
  onJump: (location: Location) => void
  /** Replaces the default "Check ATS score" button (e.g. a score badge). */
  trigger?: React.ReactNode
}

export function AtsPanel({ resumeId, open, onOpenChange, saveNow, lastSavedAt, onJump, trigger }: AtsPanelProps) {
  const latest = useLatestAnalysis(resumeId, open)
  const run = useRunAnalysis(resumeId)
  const [jobDescription, setJobDescription] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const analysis = latest.data ?? null
  const jd = jobDescription ?? analysis?.job_description ?? ''
  const stale = analysis && lastSavedAt && lastSavedAt > new Date(analysis.created_at)
  // Closing via a fix link moves focus into the editor, so don't return it to the trigger.
  const jumping = useRef(false)
  const jump = (location: Location) => {
    jumping.current = true
    onJump(location)
  }

  const onRun = async () => {
    setError(null)
    if (!(await saveNow())) {
      setError('Fix the highlighted fields in the editor first, then check again.')
      return
    }
    try {
      await run.mutateAsync({ jobDescription: jd.trim() || null })
    } catch (err) {
      setError(apiErrorMessage(err, {}, { useServerDetail: true }))
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetTrigger asChild>
        {trigger ?? (
          <Button type="button" variant="outline" size="sm">
            <Gauge />
            Check ATS score
          </Button>
        )}
      </SheetTrigger>
      <SheetContent
        className="w-full gap-0 overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-xl"
        onCloseAutoFocus={(event) => {
          if (jumping.current) event.preventDefault()
          jumping.current = false
        }}
      >
        <SheetHeader className="border-b">
          <SheetTitle>ATS check</SheetTitle>
          <SheetDescription>
            Rule-based checks you can trace point by point, plus keyword matching and a recruiter review.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-6 p-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="ats-jd">Job description (optional)</Label>
            <Textarea
              id="ats-jd"
              rows={5}
              maxLength={MAX_JD}
              placeholder="Paste a job posting to see which of its keywords your resume covers."
              value={jd}
              onChange={(event) => setJobDescription(event.target.value)}
            />
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {jd ? `${jd.length.toLocaleString()} / ${MAX_JD.toLocaleString()}` : 'Without one, we compare against your target role.'}
              </span>
              <Button type="button" onClick={() => void onRun()} disabled={run.isPending}>
                {run.isPending && <Loader2 className="animate-spin" />}
                {run.isPending ? 'Checking…' : analysis ? 'Check again' : 'Check ATS score'}
              </Button>
            </div>
            {run.isPending && (
              <p className="text-xs text-muted-foreground" aria-live="polite">
                Running checks and the recruiter review. This usually takes 10–30 seconds.
              </p>
            )}
            <FormError message={error} />
          </div>

          {latest.isPending && open && <p className="text-sm text-muted-foreground">Loading last result…</p>}
          {latest.isSuccess && !analysis && !run.isPending && (
            <p className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
              No check yet. Run one to see your score.
            </p>
          )}

          {analysis && (
            <>
              <section aria-label="Score" className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:gap-6">
                <ScoreRing score={analysis.score} />
                <div className="w-full flex-1">
                  <CategoryMeters categories={analysis.report.categories} previous={analysis.previous?.categories} />
                </div>
              </section>
              <p className="-mt-3 text-center text-xs text-muted-foreground sm:text-left">
                Checked {formatRelativeTime(analysis.created_at)}
                {analysis.previous && (
                  <>
                    {' · '}Was {analysis.previous.score} before <Delta value={analysis.score - analysis.previous.score} />
                  </>
                )}
                {stale && ' · You’ve edited since. Check again for an up-to-date score.'}
              </p>

              <PanelSection title="Fix these first">
                <FixList fixes={analysis.report.fixes} onJump={jump} />
              </PanelSection>
              <PanelSection title="Keywords">
                <KeywordChips keywords={analysis.report.keywords} />
              </PanelSection>
              <PanelSection title="Recruiter review">
                <AIReviewPanel report={analysis.report} />
              </PanelSection>
              <PanelSection title="All checks">
                <ul className="flex flex-col gap-1.5 text-sm">
                  {analysis.report.checks.map((check) => (
                    <li key={check.id} className="flex items-start gap-2">
                      <span className="w-12 shrink-0 text-xs font-medium text-muted-foreground uppercase">
                        {check.status}
                      </span>
                      <span className="flex-1">{check.title}</span>
                      {check.points_lost > 0 && (
                        <span className="text-xs text-muted-foreground tabular-nums">−{check.points_lost}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </PanelSection>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function PanelSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  )
}
