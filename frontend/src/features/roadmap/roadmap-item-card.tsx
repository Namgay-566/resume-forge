import { ChevronDown, Clock, ExternalLink, Hammer, Loader2, RefreshCw, ShieldCheck, Sparkles, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { StatusBadge } from '@/features/skill-gap/status-badge'
import { NoCuratedResource } from '@/components/no-resource'
import { isProofType, PROOF_TYPES } from '@/features/proofs/proof-types'
import { cn } from '@/lib/utils'
import { notifyError } from '@/lib/notify'

import { useProjectIdea, useSetPlanStatus } from './api'
import type { PlanStatus, RoadmapItem } from './types'

const PLAN_OPTIONS: { value: PlanStatus; label: string }[] = [
  { value: 'not_started', label: 'Not started' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'done', label: 'Done' },
]
const IMPORTANCE = { critical: 'Critical', important: 'Important', nice_to_have: 'Nice to have' } as const
const RESOURCE_TYPE = { course: 'Course', docs: 'Docs', tutorial: 'Tutorial', video: 'Video' } as const

interface RoadmapItemCardProps {
  item: RoadmapItem
  step: number
  resumeId: string
  roleName: string
  defaultOpen: boolean
}

export function RoadmapItemCard({ item, step, resumeId, roleName, defaultOpen }: RoadmapItemCardProps) {
  const [open, setOpen] = useState(defaultOpen)
  const [showAll, setShowAll] = useState(false)
  const setStatus = useSetPlanStatus(resumeId)
  const project = useProjectIdea(resumeId)
  const done = item.plan_status === 'done'
  const needsLearning = item.gap_status === 'missing' || item.gap_status === 'inferred'
  const resources = showAll ? item.resources : item.resources.slice(0, 3)
  const proofUrl = `/proof-vault?${new URLSearchParams({ skill: item.slug, name: item.name, resume: resumeId })}`
  const detailsId = `roadmap-${item.slug}-details`

  return (
    <div className={cn('rounded-xl border bg-card shadow-xs transition-opacity', done && 'opacity-80')}>
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Step {step}</p>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className={cn('font-semibold', done && 'line-through decoration-muted-foreground')}>{item.name}</h3>
              <span className="text-xs text-muted-foreground">{IMPORTANCE[item.importance]}</span>
              <StatusBadge status={item.gap_status} />
            </div>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="size-3" aria-hidden />
              ~{item.hours.total} h
              {needsLearning ? ` (${item.hours.learn} h learning + ${item.hours.project} h project)` : ' (proof project)'}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-expanded={open}
            aria-controls={detailsId}
            aria-label={open ? `Hide plan for ${item.name}` : `Show plan for ${item.name}`}
            onClick={() => setOpen((o) => !o)}
          >
            <ChevronDown className={cn('transition-transform', open && 'rotate-180')} />
          </Button>
        </div>

        <RadioGroup
          value={item.plan_status}
          onValueChange={(value) => {
            setStatus.mutate(
              { skillId: item.skill_id, status: value as PlanStatus },
              { onError: (err) => notifyError('Couldn’t update your roadmap', err) },
            )
          }}
          aria-label={`Progress on ${item.name}`}
          className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1"
        >
          {PLAN_OPTIONS.map((option) => (
            <label
              key={option.value}
              htmlFor={`${item.slug}-${option.value}`}
              className="flex cursor-pointer items-center justify-center rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground has-data-[state=checked]:bg-background has-data-[state=checked]:text-foreground has-data-[state=checked]:shadow-sm"
            >
              <RadioGroupItem id={`${item.slug}-${option.value}`} value={option.value} className="sr-only" />
              {option.label}
            </label>
          ))}
        </RadioGroup>
      </div>

      {open && (
        <div id={detailsId} className="flex flex-col gap-5 border-t p-4">
          {needsLearning && (
            <Part title="1. Learn" icon={<Sparkles className="size-4" aria-hidden />}>
              {item.resources.length === 0 ? (
                <NoCuratedResource phrase={item.search_phrase} />
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {resources.map((r) => (
                    <li key={r.id}>
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                      >
                        <span className="min-w-0">
                          <span className="font-medium group-hover:underline">{r.title}</span>
                          <span className="text-muted-foreground">
                            {' '}· {r.provider} · {RESOURCE_TYPE[r.type]} · <span className="capitalize">{r.level}</span>
                            {r.est_hours && ` · ~${Number(r.est_hours)} h`}
                          </span>
                        </span>
                        <span className="flex shrink-0 items-center gap-1.5 text-xs">
                          {r.is_free && <span className="rounded bg-success-muted px-1.5 text-success-text">Free</span>}
                          <ExternalLink className="size-3.5 text-muted-foreground" aria-label="opens in a new tab" />
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              {item.resources.length > 3 && (
                <Button type="button" variant="link" size="sm" className="h-auto self-start p-0" onClick={() => setShowAll((s) => !s)}>
                  {showAll ? 'Show fewer' : `Show all ${item.resources.length} resources`}
                </Button>
              )}
            </Part>
          )}

          <Part title={needsLearning ? '2. Prove it' : '1. Prove it'} icon={<Hammer className="size-4" aria-hidden />}>
            {item.project ? (
              <div className="flex flex-col gap-2 rounded-lg bg-muted/50 p-3">
                <p className="font-medium">{item.project.title}</p>
                <p className="text-sm text-muted-foreground">{item.project.summary}</p>
                <ProjectDeliverable deliverable={item.project.deliverable ?? null} proofType={item.project.proof_type ?? null} />
                <ol className="list-decimal pl-5 text-sm">
                  {item.project.steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
                {item.project.stretch && <p className="text-sm"><span className="font-medium">Stretch:</span> {item.project.stretch}</p>}
                <p className="text-xs text-muted-foreground">
                  ~{item.project.est_hours} h
                  {item.project.tailored_for && ` · tailored for ${item.project.tailored_for}`}
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="self-start"
                  disabled={project.isPending}
                  onClick={() => project.mutate({ skillId: item.skill_id, regenerate: true })}
                >
                  {project.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                  Different idea
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-start gap-2">
                <p className="text-sm text-muted-foreground">
                  A small portfolio project that proves {item.name} for a {roleName} role.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={project.isPending}
                  onClick={() => project.mutate({ skillId: item.skill_id, regenerate: false })}
                >
                  {project.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
                  {project.isPending ? 'Designing a project…' : 'Get a project idea'}
                </Button>
              </div>
            )}
            {project.isError && (
              <FormError message={apiErrorMessage(project.error, {}, { useServerDetail: true })} />
            )}
          </Part>

          <Part title={needsLearning ? '3. Prove' : '2. Prove'} icon={<ShieldCheck className="size-4" aria-hidden />}>
            <p className="text-sm">
              Upload one of:{' '}
              <span className="font-medium">
                {item.proof.accepted.map((t) => PROOF_TYPES[t]?.label ?? t).join(' · ')}
              </span>
            </p>
            <ul className="list-disc pl-5 text-sm">
              {item.proof.must_include.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
            {item.project && (
              <div>
                <p className="text-sm font-medium">A reviewer will also check</p>
                <ul className="list-disc pl-5 text-sm text-muted-foreground">
                  {item.project.reviewer_checks.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
            <Button asChild size="sm" variant="outline" className="self-start">
              <Link to={proofUrl}>
                <Upload />
                Upload proof
              </Link>
            </Button>
          </Part>
        </div>
      )}
    </div>
  )
}

function Part({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h4 className="flex items-center gap-1.5 text-sm font-semibold">
        {icon}
        {title}
      </h4>
      {children}
    </section>
  )
}

/** "You'll end up with: a 2-page case study · upload it as a work sample". */
function ProjectDeliverable({ deliverable, proofType }: { deliverable: string | null; proofType: string | null }) {
  const kind = isProofType(proofType) ? PROOF_TYPES[proofType] : null
  const what = deliverable ?? kind?.label.toLowerCase()
  if (!what) return null
  return (
    <p className="text-sm">
      <span className="font-medium">You&apos;ll end up with:</span> {what}
      {kind && <span className="text-muted-foreground"> · upload it as {kind.short}</span>}
    </p>
  )
}