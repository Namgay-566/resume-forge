import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'

import { ProgressMeter } from '@/components/progress-meter'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useResumes } from '@/features/resumes/api'
import { useRoadmap } from '@/features/roadmap/api'
import { RoadmapItemCard } from '@/features/roadmap/roadmap-item-card'
import { RoadmapTimeline } from '@/features/roadmap/roadmap-timeline'
import { PageHeader } from '@/components/page-header'

export function RoadmapPage() {
  const resumes = useResumes()
  const [params, setParams] = useSearchParams()
  const resumeId = params.get('resume') ?? resumes.data?.[0]?.id ?? null
  const roadmap = useRoadmap(resumeId)
  const noRole = isAxiosError(roadmap.error) && roadmap.error.response?.status === 409
  // Links like /roadmap#roadmap-git open and scroll to that item once the data has loaded.
  const target = useLocation().hash.replace(/^#roadmap-/, '')
  const linked = roadmap.data?.items.find((i) => i.slug === target)
  const firstOpen = (linked ?? roadmap.data?.items.find((i) => i.plan_status !== 'done'))?.skill_id
  
  // NEW: State for showing all or just the top 3
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    if (!linked) return
    document.getElementById(`roadmap-${linked.slug}`)?.scrollIntoView({ block: 'start' })
  }, [linked])

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader title="Roadmap" description="Your skill gaps in the order that matters most: learn, do a proof project that fits your field, get verified." />

      {resumes.data && resumes.data.length > 1 && (
        <div className="flex max-w-sm flex-col gap-1.5">
          <Label htmlFor="roadmap-resume">Resume</Label>
          <Select value={resumeId ?? undefined} onValueChange={(id) => setParams({ resume: id })}>
            <SelectTrigger id="roadmap-resume" className="w-full">
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
        </div>
      )}

      {(resumes.isPending || roadmap.isPending) && resumeId !== null && (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading roadmap">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-24 rounded-xl" />
        </div>
      )}
      {resumes.data?.length === 0 && (
        <EmptyState text="Create or import a resume and choose a target role to get a roadmap.">
          <Button asChild>
            <Link to="/resumes">Go to My Resumes</Link>
          </Button>
        </EmptyState>
      )}
      {noRole && (
        <EmptyState text="This resume has no target role yet. Choose one to build your roadmap.">
          <Button asChild>
            <Link to={`/resumes/${resumeId}`}>Choose a target role</Link>
          </Button>
        </EmptyState>
      )}
      {roadmap.isError && !noRole && <FormError message={apiErrorMessage(roadmap.error)} />}

      {roadmap.data && (
        <>
          <section aria-label="Progress" className="flex flex-col gap-3 rounded-xl border bg-card p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p>
                <span className="text-sm text-muted-foreground">Towards </span>
                <span className="font-semibold">{roadmap.data.role.name}</span>
              </p>
              <Link to={`/skill-gap?resume=${roadmap.data.resume_id}`} className="text-sm underline-offset-4 hover:underline">
                Readiness {roadmap.data.readiness}/100
              </Link>
            </div>
            <ProgressMeter value={roadmap.data.totals.done} max={roadmap.data.totals.items} label="Roadmap items done" />
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {roadmap.data.totals.done} of {roadmap.data.totals.items} done
              </span>
              {roadmap.data.totals.in_progress > 0 && ` · ${roadmap.data.totals.in_progress} in progress`}
              {` · about ${roadmap.data.totals.hours_remaining} h left of ${roadmap.data.totals.hours_total} h`}
            </p>
            <p className="text-xs text-muted-foreground">
              Marking an item done tracks your progress. A skill counts as Verified once its proof is reviewed.
            </p>
          </section>

          {roadmap.data.items.length === 0 ? (
            <EmptyState text={`Every skill for ${roadmap.data.role.name} is verified. Nice work.`}>
              <Button asChild variant="outline">
                <Link to="/skill-gap">See Skill Gap</Link>
              </Button>
            </EmptyState>
          ) : (
            <>
              <h2 className="sr-only">Your plan, skill by skill</h2>
              
              {/* NEW: Display only top 3 unless showAll is true */}
              <RoadmapTimeline
                items={showAll ? roadmap.data.items : roadmap.data.items.slice(0, 3)}
                resumeId={roadmap.data.resume_id}
                renderBody={(item, step) => (
                  <RoadmapItemCard
                    item={item}
                    step={step}
                    resumeId={roadmap.data.resume_id}
                    roleName={roadmap.data.role.name}
                    defaultOpen={item.skill_id === firstOpen}
                  />
                )}
              />
              
              {roadmap.data.items.length > 3 && !showAll && (
                <Button 
                  variant="outline" 
                  className="mt-2 self-center" 
                  onClick={() => setShowAll(true)}
                >
                  Show all {roadmap.data.items.length} skills
                </Button>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

function EmptyState({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed px-6 py-12 text-center">
      <p className="max-w-md text-sm text-muted-foreground">{text}</p>
      {children}
    </div>
  )
}