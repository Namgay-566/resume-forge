import { ArrowRight, FilePlus2, FileText, Upload } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardResume } from '@/features/roadmap/types'
import { formatRelativeTime } from '@/lib/format'

export function ResumesList({ resumes, total }: { resumes: DashboardResume[]; total: number }) {
  return (
    <Card className="gap-3 px-5 py-5 sm:px-6">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-h4">
          <FileText className="size-4 text-primary" aria-hidden /> Your resumes
        </h2>
        <Button asChild variant="link" size="sm">
          <Link to="/resumes">
            {total > resumes.length ? `All ${total}` : 'Manage'} <ArrowRight />
          </Link>
        </Button>
      </div>
      <ul className="-mx-2 flex flex-col">
        {resumes.map((r) => (
          <li key={r.id}>
            <Link
              to={`/resumes/${r.id}`}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-xl px-2 py-2.5 transition-colors outline-none hover:bg-muted/70 focus-visible:ring-3 focus-visible:ring-ring/40 sm:grid-cols-[auto_1fr_auto_auto]"
            >
              <span className="flex size-9 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                <FileText className="size-4" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{r.title}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {r.target_role?.name ?? 'No target role'} · edited {formatRelativeTime(r.updated_at)}
                </span>
              </span>
              <span className="hidden items-center gap-4 sm:flex">
                <Mini label="ATS" value={r.ats_score} color="var(--series-ats)" />
                <Mini label="Ready" value={r.readiness} color="var(--series-readiness)" suffix="%" />
              </span>
              <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Mini({ label, value, color, suffix = '' }: { label: string; value: number | null; color: string; suffix?: string }) {
  return (
    <span className="flex w-16 flex-col items-end">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1.5 text-sm font-semibold tabular-nums">
        <span className="size-1.5 rounded-full" style={{ background: value === null ? 'var(--muted-foreground)' : color }} aria-hidden />
        {value === null ? '–' : `${value}${suffix}`}
      </span>
    </span>
  )
}

/** Whole-dashboard empty state for someone with no resumes yet. */
export function NoResumes() {
  return (
    <Card variant="elevated" className="px-5 sm:px-6">
      <EmptyState
        icon={FilePlus2}
        title="No resumes yet. Build your first one."
        description="Start from scratch or import the resume you already have. Your ATS score, skill gap and roadmap all start here."
        actions={
          <>
            <Button asChild>
              <Link to="/resumes?new=1">
                <FilePlus2 /> Build my resume
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/resumes?import=1">
                <Upload /> Import PDF or DOCX
              </Link>
            </Button>
          </>
        }
      />
    </Card>
  )
}

export function ResumesSkeleton() {
  return (
    <Card className="gap-3 px-5 py-5 sm:px-6" aria-hidden>
      <Skeleton className="h-5 w-32" />
      {[0, 1].map((i) => (
        <div key={i} className="flex items-center gap-3 py-2.5">
          <Skeleton className="size-9 rounded-lg" />
          <div className="flex flex-1 flex-col gap-1.5">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="hidden h-8 w-32 sm:block" />
        </div>
      ))}
    </Card>
  )
}
