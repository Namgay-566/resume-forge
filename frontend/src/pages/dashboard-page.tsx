import { Gauge, Target } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useAuth } from '@/features/auth/use-auth'
import { NextActionCard, NextActionSkeleton } from '@/features/dashboard/next-action-card'
import { RecentProofs } from '@/features/dashboard/recent-proofs'
import { NoResumes, ResumesList, ResumesSkeleton } from '@/features/dashboard/resumes-list'
import { RoadmapCard, RoadmapSkeleton } from '@/features/dashboard/roadmap-card'
import { ScoreCard, ScoreCardSkeleton } from '@/features/dashboard/score-card'
import { ScoreHistoryCard, ScoreHistorySkeleton } from '@/features/dashboard/score-history-card'
import { atsBand, focusResume, lastDelta, readinessBand, statusLine } from '@/features/dashboard/status'
import { WelcomeHeader } from '@/features/dashboard/welcome-header'
import { useDashboard } from '@/features/roadmap/api'
import type { DashboardSummary } from '@/features/roadmap/types'

export function DashboardPage() {
  const { user } = useAuth()
  const summary = useDashboard()
  const data = summary.data

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <WelcomeHeader name={user?.name} status={data ? statusLine(data) : summary.isError ? '' : null} />

      {summary.isError && (
        <div className="flex flex-col items-start gap-2">
          <FormError message={apiErrorMessage(summary.error)} />
          <Button variant="outline" size="sm" onClick={() => void summary.refetch()}>
            Try again
          </Button>
        </div>
      )}

      {summary.isPending && <DashboardSkeleton />}
      {data && (data.resume_count === 0 ? <FirstRun data={data} /> : <Overview data={data} />)}
    </div>
  )
}

function Overview({ data }: { data: DashboardSummary }) {
  const focus = focusResume(data)
  const resumeId = data.resume_id ?? focus?.id ?? ''
  return (
    <>
      <NextActionCard action={data.next_action} />
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <ScoreCard
          title="ATS score"
          icon={Gauge}
          value={data.ats_score}
          color="var(--series-ats)"
          band={data.ats_score === null ? null : atsBand(data.ats_score)}
          delta={focus ? lastDelta(focus.ats_history) : null}
          context={data.resume_title ? `For “${data.resume_title}”` : null}
          emptyHint="Not checked yet. See how applicant tracking systems read your resume."
          unit="/ 100"
          action={{ label: data.ats_score === null ? 'Run your first check' : 'Check again', to: `/resumes/${resumeId}?ats=open` }}
        />
        <ScoreCard
          title="Role readiness"
          icon={Target}
          value={data.readiness}
          color="var(--series-readiness)"
          band={data.readiness === null ? null : readinessBand(data.readiness)}
          delta={focus ? lastDelta(focus.readiness_history) : null}
          context={data.role ? `For ${data.role.name}` : null}
          emptyHint="Choose a target role to measure how ready you are."
          unit="% ready"
          action={
            data.role
              ? { label: 'See skill gap', to: `/skill-gap?resume=${resumeId}` }
              : { label: 'Choose a target role', to: `/resumes/${resumeId}` }
          }
        />
        <div className="md:col-span-2 xl:col-span-1">
          <RoadmapCard data={data} />
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr]">
        <ScoreHistoryCard resumes={data.resumes} defaultResumeId={data.resume_id} />
        <RecentProofs />
      </div>
      <ResumesList resumes={data.resumes} total={data.resume_count} />
    </>
  )
}

function FirstRun({ data }: { data: DashboardSummary }) {
  return (
    <>
      <NextActionCard action={data.next_action} />
      <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr]">
        <NoResumes />
        <RecentProofs />
      </div>
    </>
  )
}

/** Same grid as the real dashboard, so nothing jumps when data arrives. */
function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading dashboard">
      <NextActionSkeleton />
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <ScoreCardSkeleton />
        <ScoreCardSkeleton />
        <div className="md:col-span-2 xl:col-span-1">
          <RoadmapSkeleton />
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr]">
        <ScoreHistorySkeleton />
        <ResumesSkeleton />
      </div>
    </div>
  )
}
