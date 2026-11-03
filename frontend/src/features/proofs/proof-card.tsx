import { Link } from 'react-router'

import { GitHubMark } from '@/components/icons/github-mark'
import { formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import { AnalysisProgress } from './analysis-progress'
import { ProofBadge, proofTitle } from './proof-badge'
import { PROOF_TYPES } from './proof-types'
import { isRunning, type Proof } from './types'


function scoreTone(score: number) {
  return score >= 70 ? 'text-success-text' : score >= 50 ? 'text-warning-text' : 'text-danger-text'
}

export function ProofCard({ proof }: { proof: Proof }) {
  const { icon, label } = PROOF_TYPES[proof.type]
  const Icon = proof.type === 'github_repo' ? GitHubMark : icon
  const running = isRunning(proof.status)
  return (
    <li
      className={cn(
        'group relative flex flex-col gap-4 rounded-2xl border bg-card p-5 shadow-xs transition-[box-shadow,border-color] focus-within:ring-3 focus-within:ring-ring/40 hover:border-foreground/15 hover:shadow-md',
        running && 'border-info/30',
      )}
    >
      <div className="flex items-start gap-3">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl border bg-muted/60 text-foreground">
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
          {/* The whole card is the link (stretched), with the title as its accessible name. */}
          <Link to={`/proof-vault/${proof.id}`} className="block truncate font-semibold outline-none after:absolute after:inset-0 after:rounded-2xl">
            {proofTitle(proof)}
          </Link>
        </div>
        {proof.score !== null && !running && (
          <span className="flex flex-col items-end">
            <span className={cn('font-heading text-2xl leading-none font-semibold tabular-nums', scoreTone(proof.score))}>{proof.score}</span>
            <span className="text-[11px] text-muted-foreground">score</span>
          </span>
        )}
      </div>

      {running ? (
        <AnalysisProgress proof={proof} compact />
      ) : (
        <div className="flex flex-col items-start gap-2">
          <ProofBadge proof={proof} />
          {proof.decision && <p className="line-clamp-2 text-sm text-muted-foreground">{proof.decision}</p>}
        </div>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-1.5">
        {proof.skills.slice(0, 4).map((s) => (
          <span key={s.id} className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
            {s.name}
          </span>
        ))}
        {proof.skills.length > 4 && <span className="text-xs text-muted-foreground">+{proof.skills.length - 4}</span>}
        <span className="ml-auto text-xs text-muted-foreground">{formatRelativeTime(proof.created_at)}</span>
      </div>
    </li>
  )
}
