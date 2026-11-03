import { isAxiosError } from 'axios'
import { ArrowRight, BookOpen, CircleAlert, FilePlus2, Info, Map as MapIcon, Target, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { ProgressRing } from '@/components/progress-ring'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { readinessBand } from '@/features/dashboard/status'
import { useResumes } from '@/features/resumes/api'
import { useRoadmap } from '@/features/roadmap/api'
import { RoadmapTimeline } from '@/features/roadmap/roadmap-timeline'
import { useSkillGap } from '@/features/skill-gap/api'
import { LearnSheet } from '@/features/skill-gap/learn-sheet'
import { proofAction, proofLink } from '@/features/skill-gap/links'
import { SkillCard } from '@/features/skill-gap/skill-card'
import { STATUS } from '@/features/skill-gap/status-badge'
import { AiRoleNote } from '@/features/target-roles/ai-role-note'
import { gapSummary } from '@/features/skill-gap/summary'
import { type GroupBy, IMPORTANCE_LABEL, type SkillSection, groupSkills } from '@/features/skill-gap/grouping'
import type { RoleSkillGap, SkillGapReport, SkillStatus } from '@/features/skill-gap/types'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/page-header'

const GROUP_BY: { key: GroupBy; label: string }[] = [
  { key: 'category', label: 'Category' },
  { key: 'importance', label: 'Importance' },
]
const ORDER: SkillStatus[] = ['present_verified', 'present_unverified', 'inferred', 'missing']
const BAR = { success: 'bg-success', warning: 'bg-warning', info: 'bg-info', danger: 'bg-danger' } as const
const TIMELINE_STEPS = 5

const AI_NOTE: Partial<Record<SkillGapReport['ai_status'], string>> = {
  rate_limited: 'Skills implied by your bullets weren’t checked this time (AI limit reached). Try again later.',
  unavailable: 'Skills implied by your bullets aren’t checked right now because the AI service is unavailable.',
  failed: 'Checking for skills implied by your bullets failed this time. Reload to try again.',
}

export function SkillGapPage() {
  const resumes = useResumes()
  const [params, setParams] = useSearchParams()
  const resumeId = params.get('resume') ?? resumes.data?.[0]?.id ?? null
  const gap = useSkillGap(resumeId)
  const roadmap = useRoadmap(gap.data ? resumeId : null)
  const [learning, setLearning] = useState<RoleSkillGap | null>(null)
  const [groupBy, setGroupBy] = useState<GroupBy>('category')
  const noRole = isAxiosError(gap.error) && gap.error.response?.status === 409

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <PageHeader
        title="Skill Gap"
        description="How your resume compares with what your target role needs."
        actions={
          resumes.data && resumes.data.length > 1 && (
          <Select value={resumeId ?? undefined} onValueChange={(id) => setParams({ resume: id })}>
            <SelectTrigger className="w-full sm:w-72" aria-label="Resume">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {resumes.data.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.title}
                  {r.target_role ? ` · ${r.target_role.name}` : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          )
        }
      />

      {(resumes.isPending || (gap.isPending && resumeId)) && <PageSkeleton />}
      {resumes.data?.length === 0 && (
        <Card className="px-5">
          <EmptyState
            icon={FilePlus2}
            title="No resume to compare yet"
            description="Create or import a resume, pick a target role, and your skill gap appears here."
            actions={
              <Button asChild>
                <Link to="/resumes?new=1">Build my resume</Link>
              </Button>
            }
          />
        </Card>
      )}
      {noRole && (
        <Card className="px-5">
          <EmptyState
            icon={Target}
            title="Choose a target role"
            description="Pick the job you're aiming for and we'll compare your skills against what it needs."
            actions={
              <Button asChild>
                <Link to={`/resumes/${resumeId}`}>Choose a target role</Link>
              </Button>
            }
          />
        </Card>
      )}
      {gap.isError && !noRole && <FormError message={apiErrorMessage(gap.error)} />}

      {gap.data && (
        <>
          <ReadinessHero report={gap.data} />
          {AI_NOTE[gap.data.ai_status] && (
            <p className="flex gap-2 rounded-xl bg-muted p-3 text-sm text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> {AI_NOTE[gap.data.ai_status]}
            </p>
          )}
          <MissingCritical report={gap.data} onLearn={setLearning} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-h3">Skills for {gap.data.role.name}</h2>
            <div role="group" aria-label="Group skills by" className="inline-flex rounded-lg border bg-muted p-0.5">
              {GROUP_BY.map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  size="sm"
                  variant={groupBy === option.key ? 'secondary' : 'ghost'}
                  className={cn(groupBy === option.key && 'bg-card shadow-xs')}
                  aria-pressed={groupBy === option.key}
                  onClick={() => setGroupBy(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>
          {groupSkills(gap.data.skills, groupBy).map((section) => (
            <SkillGroup
              key={section.key}
              section={section}
              resumeId={gap.data.resume_id}
              subtitle={(s) => (groupBy === 'category' ? IMPORTANCE_LABEL[s.importance] : s.group.name)}
              onLearn={setLearning}
            />
          ))}
          <section aria-labelledby="timeline-heading" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 id="timeline-heading" className="flex items-center gap-2 text-h3">
                  <MapIcon className="size-5 text-primary" aria-hidden /> Your roadmap
                </h2>
                <p className="text-sm text-muted-foreground">Most important first. Tick a step off when you&apos;ve done it.</p>
              </div>
              <Button asChild variant="link" size="sm">
                <Link to={`/roadmap?resume=${gap.data.resume_id}`}>
                  Full roadmap <ArrowRight />
                </Link>
              </Button>
            </div>
            {roadmap.isPending && <Skeleton className="h-48 rounded-xl" />}
            {roadmap.data && roadmap.data.items.length === 0 && (
              <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                Nothing left to learn for {gap.data.role.name}. Every skill is verified.
              </p>
            )}
            {roadmap.data && roadmap.data.items.length > 0 && (
              <RoadmapTimeline items={roadmap.data.items.slice(0, TIMELINE_STEPS)} resumeId={gap.data.resume_id} />
            )}
          </section>
        </>
      )}
      <LearnSheet skill={learning} resumeId={gap.data?.resume_id ?? null} onClose={() => setLearning(null)} />
    </div>
  )
}

function ReadinessHero({ report }: { report: SkillGapReport }) {
  const band = readinessBand(report.readiness)
  return (
    <Card variant="elevated" className="flex-col gap-6 px-5 py-6 sm:flex-row sm:items-center sm:px-7">
      <ProgressRing value={report.readiness} color="var(--series-readiness)" label="Role readiness" size={148} caption="% ready" className="self-center" />
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="eyebrow">Readiness for {report.role.name}</p>
            <Badge variant={band.tone}>{band.label}</Badge>
          </div>
          <p className="font-heading text-xl leading-snug font-semibold tracking-tight md:text-2xl">{gapSummary(report)}</p>
          {report.role.source === 'ai_generated' && <AiRoleNote className="mt-1" />}
        </div>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Skills by status">
          {ORDER.map((status) => {
            const s = STATUS[status]
            return (
              <li key={status} className="flex items-center gap-2.5 rounded-xl border bg-background px-3 py-2">
                <span className={cn('size-2.5 shrink-0 rounded-full', BAR[s.tone])} aria-hidden />
                <span className="min-w-0">
                  <span className="block font-heading text-lg leading-tight font-semibold tabular-nums">{report.counts[status]}</span>
                  <span className="block truncate text-xs text-muted-foreground">{s.label}</span>
                </span>
              </li>
            )
          })}
        </ul>
        <p className="text-xs text-muted-foreground">
          Critical skills count most. Verified skills earn full credit, unverified 75%, inferred 40%.
        </p>
      </div>
    </Card>
  )
}

const MISSING_TAIL = { critical: 'It’s critical for', important: 'It’s important for', nice_to_have: 'It’s a nice-to-have for' } as const

/** The gaps that cost the most: each missing critical skill gets its own call to action. */
function MissingCritical({ report, onLearn }: { report: SkillGapReport; onLearn: (s: RoleSkillGap) => void }) {
  const missing = report.skills.filter((s) => s.status === 'missing' && s.importance === 'critical')
  if (missing.length === 0) return null
  return (
    <section aria-label="Missing critical skills" className="flex flex-col gap-3">
      {missing.map((skill) => (
        <div
          key={skill.skill_id}
          className="flex flex-col gap-4 rounded-2xl border border-danger/30 bg-danger-muted p-4 sm:flex-row sm:items-center sm:p-5"
        >
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-danger text-danger-foreground">
            <CircleAlert className="size-5" aria-hidden />
          </span>
          <p className="flex-1 text-base">
            <span className="font-semibold text-danger-text">{skill.name} is missing.</span>{' '}
            <span className="text-foreground">
              {MISSING_TAIL[skill.importance]} {report.role.name}.
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => onLearn(skill)}>
              <BookOpen /> Learn it
            </Button>
            <Button asChild variant="outline" className="bg-card">
              <Link to={proofLink(skill, report.resume_id)}>
                <Upload /> {proofAction(skill)}
              </Link>
            </Button>
          </div>
        </div>
      ))}
    </section>
  )
}

function SkillGroup({
  section,
  resumeId,
  subtitle,
  onLearn,
}: {
  section: SkillSection
  resumeId: string
  subtitle: (s: RoleSkillGap) => string
  onLearn: (s: RoleSkillGap) => void
}) {
  const { skills } = section
  const covered = skills.filter((s) => s.status !== 'missing').length
  return (
    <section aria-labelledby={`group-${section.key}`} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 id={`group-${section.key}`} className="text-lg font-semibold">
            {section.title}
          </h3>
          <p className="text-sm text-muted-foreground">{section.blurb}</p>
        </div>
        <div className="flex w-full flex-col gap-1.5 sm:w-56">
          <p className="text-xs text-muted-foreground sm:text-right">
            <span className="font-semibold text-foreground">
              {covered} of {skills.length}
            </span>{' '}
            on your resume
          </p>
          {/* One segment per skill, in status order: the group at a glance. */}
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden>
            {[...skills]
              .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status))
              .map((s) => (
                <span key={s.skill_id} className={cn('flex-1', BAR[STATUS[s.status].tone])} />
              ))}
          </div>
        </div>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {skills.map((skill) => (
          <SkillCard key={skill.skill_id} skill={skill} subtitle={subtitle(skill)} resumeId={resumeId} onLearn={onLearn} />
        ))}
      </ul>
    </section>
  )
}

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading skill gap">
      <div className="flex flex-col gap-6 rounded-2xl border p-6 sm:flex-row sm:items-center">
        <Skeleton className="size-36 self-center rounded-full" />
        <div className="flex flex-1 flex-col gap-3">
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-7 w-4/5" />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
      <Skeleton className="h-20 rounded-2xl" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-32 rounded-xl" />
        ))}
      </div>
    </div>
  )
}
