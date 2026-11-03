import { ArrowRight, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useProofs } from '@/features/proofs/api'
import { ProofBadge, proofTitle } from '@/features/proofs/proof-badge'
import { PROOF_TYPES } from '@/features/proofs/proof-types'
import { formatRelativeTime } from '@/lib/format'

const SHOWN = 5

/** Latest proof results. Shares the Proof Vault's cached list, which polls while any run. */
export function RecentProofs() {
  const proofs = useProofs()
  const recent = [...(proofs.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, SHOWN)

  return (
    <Card className="gap-4 px-5 py-5 sm:px-6">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-h4">
          <ShieldCheck className="size-4 text-primary" aria-hidden /> Recent proofs
        </h2>
        {recent.length > 0 && (
          <Button asChild variant="link" size="sm">
            <Link to="/proof-vault">
              View all <ArrowRight />
            </Link>
          </Button>
        )}
      </div>
      {proofs.isPending && <ProofRowsSkeleton />}
      {proofs.isError && <p className="text-sm text-muted-foreground">Couldn&apos;t load your proofs. Try again in a moment.</p>}
      {proofs.isSuccess && recent.length === 0 && (
        <EmptyState
          size="sm"
          icon={ShieldCheck}
          title="No proofs yet"
          description="Upload a licence, certificate or piece of work to turn a skill into a verified one."
          actions={
            <Button asChild size="sm">
              <Link to="/proof-vault">Add your first proof</Link>
            </Button>
          }
        />
      )}
      {recent.length > 0 && (
        <ul className="-mx-2 flex flex-col">
          {recent.map((proof) => {
            const Icon = PROOF_TYPES[proof.type].icon
            return (
              <li key={proof.id}>
                <Link
                  to={`/proof-vault/${proof.id}`}
                  className="flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors outline-none hover:bg-muted/70 focus-visible:ring-3 focus-visible:ring-ring/40"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border bg-muted/60 text-muted-foreground">
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{proofTitle(proof)}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {proof.skills.map((s) => s.name).join(', ') || 'No skills mapped'} · {formatRelativeTime(proof.created_at)}
                    </span>
                  </span>
                  <ProofBadge proof={proof} />
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function ProofRowsSkeleton() {
  return (
    <div className="flex flex-col gap-1" aria-busy="true" aria-label="Loading proofs">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-3 py-2.5">
          <Skeleton className="size-9 rounded-lg" />
          <div className="flex flex-1 flex-col gap-1.5">
            <Skeleton className="h-4 w-2/5" />
            <Skeleton className="h-3 w-3/5" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      ))}
    </div>
  )
}
