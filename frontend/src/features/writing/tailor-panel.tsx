import { Check, Loader2, Undo2, Wand2, X } from 'lucide-react'
import { useState } from 'react'
import { useFormContext } from 'react-hook-form'

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
import { locationSection } from '@/features/ats/types'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useEditor } from '@/features/resumes/editor/editor-context'
import type { ResumeFormValues } from '@/features/resumes/form-schema'

import { useTailor } from './api'
import { applySuggestion } from './apply-suggestion'
import { SuggestionDiff } from './diff-view'
import { PlaceholderNote } from './placeholder-text'
import type { Suggestion } from './types'

type Decision = { state: 'accepted'; undo: () => void } | { state: 'rejected' } | { state: 'stale'; reason: string }

const TITLES: Record<Suggestion['kind'], string> = {
  rewrite_bullet: 'Reword a bullet',
  move_bullet_up: 'Move a bullet to the top',
  rewrite_summary: 'Rewrite your summary',
  feature_skills: 'Put these skills first',
  add_skill: 'Add a skill you already show',
}

function where(s: Suggestion) {
  const label = locationSection(s.location)
  return s.location.item_index === null ? label : `${label} #${s.location.item_index + 1}`
}

export function TailorPanel() {
  const { resumeId, saveNow } = useEditor()
  const form = useFormContext<ResumeFormValues>()
  const tailor = useTailor(resumeId)
  const [open, setOpen] = useState(false)
  const [jd, setJd] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, Decision>>({})
  const result = tailor.data

  const run = async () => {
    setError(null)
    if (jd.trim().length < 20) {
      setError('Paste the full job description (at least a few lines).')
      return
    }
    if (!(await saveNow())) {
      setError('Fix the highlighted fields in the editor first.')
      return
    }
    setDecisions({})
    tailor.mutate(jd.trim(), {
      onError: (err) => setError(apiErrorMessage(err, {}, { useServerDetail: true })),
    })
  }

  const accept = (s: Suggestion) => {
    const applied = applySuggestion(form, s)
    setDecisions((d) => ({
      ...d,
      [s.id]: applied.ok ? { state: 'accepted', undo: applied.undo } : { state: 'stale', reason: applied.reason },
    }))
  }

  const undo = (s: Suggestion) => {
    const decision = decisions[s.id]
    if (decision?.state === 'accepted') decision.undo()
    setDecisions((d) => {
      const next = { ...d }
      delete next[s.id]
      return next
    })
  }

  const pending = result?.suggestions.filter((s) => !decisions[s.id]).length ?? 0

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button type="button" variant="outline" size="sm" aria-label="Tailor to job">
          <Wand2 />
          <span className="hidden xl:inline">Tailor to job</span>
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full gap-0 overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-xl">
        <SheetHeader className="border-b">
          <SheetTitle>Tailor to a job</SheetTitle>
          <SheetDescription>
            Suggestions only. Nothing changes until you accept it, and you can undo anything you accept.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-6 p-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="tailor-jd">Job description</Label>
            <Textarea
              id="tailor-jd"
              rows={6}
              maxLength={20_000}
              value={jd}
              onChange={(event) => setJd(event.target.value)}
              placeholder="Paste the job posting you're applying for."
            />
            <Button type="button" className="self-end" onClick={() => void run()} disabled={tailor.isPending}>
              {tailor.isPending && <Loader2 className="animate-spin" />}
              {tailor.isPending ? 'Reading the job…' : result ? 'Suggest again' : 'Suggest changes'}
            </Button>
            <FormError message={error} />
          </div>

          {result && (
            <>
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {result.suggestions.length === 0
                  ? 'Your resume already lines up well with this job. Nothing to suggest.'
                  : `${result.suggestions.length} suggestions, ${pending} left to review.`}
              </p>
              <ul className="flex flex-col gap-3">
                {result.suggestions.map((s) => {
                  const decision = decisions[s.id]
                  return (
                    <li key={s.id} className="flex flex-col gap-2 rounded-lg border bg-background p-3">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="text-sm font-medium">{TITLES[s.kind]}</p>
                        <span className="text-xs text-muted-foreground">{where(s)}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{s.reason}</p>
                      <SuggestionDiff suggestion={s} />
                      <PlaceholderNote placeholders={s.placeholders} />
                      {!decision && (
                        <div className="flex gap-2">
                          <Button type="button" size="sm" onClick={() => accept(s)}>
                            <Check /> Accept
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => setDecisions((d) => ({ ...d, [s.id]: { state: 'rejected' } }))}
                          >
                            <X /> Reject
                          </Button>
                        </div>
                      )}
                      {decision?.state === 'accepted' && (
                        <p className="flex items-center gap-2 text-sm text-success-text">
                          <Check className="size-4" /> Applied
                          <Button type="button" variant="link" size="sm" className="h-auto p-0" onClick={() => undo(s)}>
                            <Undo2 /> Undo
                          </Button>
                        </p>
                      )}
                      {decision?.state === 'rejected' && (
                        <p className="flex items-center gap-2 text-sm text-muted-foreground">
                          Rejected
                          <Button type="button" variant="link" size="sm" className="h-auto p-0" onClick={() => undo(s)}>
                            Reconsider
                          </Button>
                        </p>
                      )}
                      {decision?.state === 'stale' && <p className="text-sm text-warning-text">{decision.reason}</p>}
                    </li>
                  )
                })}
              </ul>
              {result.gaps.length > 0 && (
                <section className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold">The job asks for, but your resume doesn't show</h3>
                  <ul className="flex flex-wrap gap-1.5">
                    {result.gaps.map((gap) => (
                      <li key={gap} className="rounded-full border border-dashed px-2.5 py-1 text-xs">
                        {gap}
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-muted-foreground">
                    Don't add these unless they're true. Check the Skill Gap page for a proof project instead.
                  </p>
                </section>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
