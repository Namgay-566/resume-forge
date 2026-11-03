import { ArrowRight, BookOpen, Check, FileBadge, FolderGit2, Gauge, ListPlus, Loader2, ShieldCheck, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useFormContext } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { useLatestAnalysis, useRunAnalysis } from '@/features/ats/api'
import { Delta } from '@/features/ats/score-delta'
import { VerificationBadge } from '@/features/proofs/verification-level'
import type { SaveStatus } from '@/features/resumes/editor/use-autosave'
import { projectForm, type ResumeFormValues } from '@/features/resumes/form-schema'
import { notifyError, notifySuccess } from '@/lib/notify'

import { useDismissSuggestion, useResumeSuggestions } from './api'
import { withBullet, withSectionEntry } from './apply'
import { ProjectDraftDialog, type ProjectEntry } from './project-draft-dialog'
import type { ResumeSuggestion } from './types'

const opts = { shouldDirty: true, shouldValidate: true } as const
const ICON = {
  add_skill: ShieldCheck, link_skill_proof: ShieldCheck, add_project: FolderGit2, add_certification: FileBadge,
  add_section_entry: BookOpen, add_bullet: ListPlus,
}

function doneMessage(s: ResumeSuggestion): string {
  switch (s.kind) {
    case 'add_project': return 'Project added to your resume'
    case 'add_certification': return 'Added to Licenses & Certifications'
    case 'link_skill_proof': return 'Proof linked to the skill'
    case 'add_section_entry': return `Added to ${s.section_heading ?? 'your resume'}`
    case 'add_bullet': return `Bullet added to ${s.target?.label || 'the entry'}`
    default: return `${s.skill_name ?? 'Skill'} added to Skills`
  }
}

const ACTION: Partial<Record<ResumeSuggestion['kind'], string>> = { link_skill_proof: 'Link proof', add_bullet: 'Add bullet' }

interface SuggestionsPanelProps {
  resumeId: string
  saveStatus: SaveStatus
}

/** "Basic Life Support is now verified. Add it to Skills?" and friends. Nothing changes until accepted. */
export function SuggestionsPanel({ resumeId, saveStatus }: SuggestionsPanelProps) {
  const form = useFormContext<ResumeFormValues>()
  const suggestions = useResumeSuggestions(resumeId)
  const dismiss = useDismissSuggestion(resumeId)
  const latest = useLatestAnalysis(resumeId, true)
  const recheck = useRunAnalysis(resumeId)
  const [accepted, setAccepted] = useState<string[]>([])
  const [drafting, setDrafting] = useState<ResumeSuggestion | null>(null)
  const pendingRecheck = useRef(false)
  const [stale, setStale] = useState<string | null>(null)

  // After accepted changes are saved, re-score (free: no AI review) to show the difference.
  const { mutate: runRecheck } = recheck
  const lastJd = latest.data?.job_description ?? null
  const hasAnalysis = Boolean(latest.data)
  useEffect(() => {
    if (!pendingRecheck.current || saveStatus !== 'saved') return
    pendingRecheck.current = false
    if (hasAnalysis) runRecheck({ jobDescription: lastJd, review: false })
  }, [saveStatus, hasAnalysis, lastJd, runRecheck])

  const done = (s: ResumeSuggestion) => {
    notifySuccess(doneMessage(s))
    setAccepted((a) => [...a, s.id])
    pendingRecheck.current = true
  }

  const accept = (s: ResumeSuggestion) => {
    setStale(null)
    const skills = form.getValues('data.skills')
    if (s.kind === 'add_skill' && s.skill_name) {
      form.setValue('data.skills', [...skills, { name: s.skill_name, skill_id: s.skill_id, proof_id: s.proof_id }], opts)
      return done(s)
    }
    if (s.kind === 'link_skill_proof' && s.skill_index !== null) {
      const entry = skills[s.skill_index]
      if (!entry || entry.name.trim() !== (s.resume_skill_name ?? '').trim()) {
        return setStale('Your Skills changed since this suggestion. Save and refresh to see it again.')
      }
      form.setValue(`data.skills.${s.skill_index}`, { ...entry, skill_id: s.skill_id, proof_id: s.proof_id }, opts)
      return done(s)
    }
    if (s.kind === 'add_certification' && s.certification) {
      const c = s.certification
      form.setValue('data.certifications', [
        ...form.getValues('data.certifications'),
        {
          name: c.name, issuer: c.issuer ?? '', issue_date: c.issue_date ?? '', credential_id: c.credential_id ?? '',
          credential_url: c.credential_url ?? '', proof_id: c.proof_id,
        },
      ], opts)
      return done(s)
    }
    if (s.kind === 'add_section_entry' && s.entry && s.section_kind) {
      const sections = withSectionEntry(form.getValues('data.sections'), s.section_kind, s.entry)
      if (!sections) return setStale(`${s.section_heading ?? 'That section'} is full. Remove an entry first.`)
      form.setValue('data.sections', sections, opts)
      return done(s)
    }
    if (s.kind === 'add_bullet' && s.target && s.bullet) {
      const result = withBullet(form.getValues('data'), s.target, s.bullet)
      if (!result) return setStale(`“${s.target.label || s.target.item_title}” changed since this suggestion. Save and refresh to see it again.`)
      form.setValue(result.path as 'data.experience.0.bullets', result.bullets, opts)
      return done(s)
    }
    if (s.kind === 'add_project' && s.project) {
      form.setValue('data.projects', [...form.getValues('data.projects'), projectForm(s.project)], opts)
      return done(s)
    }
    if (s.kind === 'add_project') setDrafting(s)
  }

  const addProject = (entry: ProjectEntry) => {
    if (!drafting) return
    form.setValue('data.projects', [
      ...form.getValues('data.projects'),
      {
        name: entry.name, description: entry.description, bullets: entry.bullets.map((value) => ({ value })),
        tools_and_skills: entry.tools_and_skills.join(', '), link: entry.link, proof_id: drafting.proof_id,
      },
    ], opts)
    done(drafting)
    setDrafting(null)
  }

  const visible = (suggestions.data?.suggestions ?? []).filter((s) => !accepted.includes(s.id))
  const result = recheck.data
  if (visible.length === 0 && !result && !recheck.isPending) return null

  return (
    <section aria-labelledby="suggestions-heading" className="flex flex-col gap-3 rounded-xl border border-success/30 bg-success-muted p-4">
      <h2 id="suggestions-heading" className="flex items-center gap-2 font-semibold">
        <ShieldCheck className="size-4 text-success-text" aria-hidden /> From your proofs
      </h2>
      {(recheck.isPending || result) && <RecheckResult pending={recheck.isPending} result={result} />}
      {stale && <p className="text-sm text-warning-text">{stale}</p>}
      <ul className="grid gap-2 lg:grid-cols-2">
        {visible.map((s) => {
          const Icon = ICON[s.kind]
          return (
            <li key={s.id} className="flex flex-col gap-2 rounded-lg border bg-background p-3">
              <div className="flex items-start gap-2">
                <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{s.title}</p>
                  {s.detail && <p className="text-xs text-muted-foreground">{s.detail}</p>}
                </div>
                {s.level && <VerificationBadge level={s.level} />}
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" onClick={() => accept(s)}>
                  <Check /> {s.kind === 'add_project' && !s.project ? 'Draft entry' : (ACTION[s.kind] ?? 'Add')}
                </Button>
                <Button type="button" size="sm" variant="ghost" disabled={dismiss.isPending} onClick={() =>
                    dismiss.mutate(s.id, {
                      onSuccess: () => notifySuccess('Suggestion hidden', 'It won’t be suggested for this resume again.'),
                      onError: (err) => notifyError('Couldn’t hide the suggestion', err),
                    })
                  }>
                  <X /> Not now
                </Button>
              </div>
            </li>
          )
        })}
      </ul>
      <ProjectDraftDialog
        key={drafting?.id ?? 'closed'}
        resumeId={resumeId}
        proofId={drafting?.proof_id ?? null}
        onClose={() => setDrafting(null)}
        onAccept={addProject}
      />
    </section>
  )
}

function RecheckResult({ pending, result }: { pending: boolean; result: ReturnType<typeof useRunAnalysis>['data'] }) {
  if (pending || !result) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
        <Loader2 className="size-4 animate-spin" /> Re-checking your ATS score…
      </p>
    )
  }
  const before = result.previous?.score
  const delta = before === undefined ? null : result.score - before
  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-background p-3" aria-live="polite">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <Gauge className="size-4 text-muted-foreground" aria-hidden />
        <span className="font-medium">ATS score</span>
        {before !== undefined && (
          <>
            <span className="tabular-nums">{before}</span>
            <ArrowRight className="size-3.5" aria-label="to" />
          </>
        )}
        <span className="font-semibold tabular-nums">{result.score}</span>
        {delta !== null && <Delta value={delta} />}
      </p>
      {result.previous && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {result.report.categories.map((c) => {
            const prev = result.previous?.categories.find((p) => p.key === c.key)?.score
            if (c.score === null || prev === null || prev === undefined) return null
            return (
              <li key={c.key}>
                {c.label} {prev} → {c.score} {c.score !== prev && <Delta value={c.score - prev} />}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
