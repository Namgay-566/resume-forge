import { Plus, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { GitHubMark } from '@/components/icons/github-mark'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useAuth } from '@/features/auth/use-auth'
import { AddProofForm } from '@/features/proofs/add-proof-form'
import { isProofType } from '@/features/proofs/proof-types'
import { useProofs } from '@/features/proofs/api'
import { ProofCard } from '@/features/proofs/proof-card'
import { LEVELS } from '@/features/proofs/verification-level'
import { PageHeader } from '@/components/page-header'

const GITHUB_LOGIN_URL = `${import.meta.env.VITE_API_URL}/auth/github/login`

export function ProofVaultPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const type = params.get('type')
  const proofs = useProofs()
  // Arriving from "Upload proof" (skill gap, roadmap) opens the form with the skill picked.
  const [adding, setAdding] = useState(() => params.has('skill'))
  const verified = proofs.data?.filter((p) => p.status === 'verified').length ?? 0

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <PageHeader
        title="Proof Vault"
        description="Real work that proves your skills. Verified skills go on your resume with the proof link."
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus /> Add proof
          </Button>
        }
      />

      {/* Only relevant once they've added a repository: most careers never need GitHub. */}
      {user && !user.github_username && proofs.data?.some((p) => p.type === 'github_repo') && (
        <div className="flex flex-col gap-3 rounded-2xl border border-warning/40 bg-warning-muted p-4 sm:flex-row sm:items-center">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-card">
            <GitHubMark className="size-5" aria-hidden />
          </span>
          <p className="flex-1 text-sm">
            <span className="font-semibold">Connect GitHub to get repositories verified.</span> We need to confirm they&apos;re
            yours. Log in with GitHub using the same email and it links to this account.
          </p>
          <Button asChild variant="outline" size="sm" className="bg-card">
            <a href={GITHUB_LOGIN_URL}>Continue with GitHub</a>
          </Button>
        </div>
      )}

      {proofs.data && proofs.data.length > 0 && (
        <p className="text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">{proofs.data.length}</span> proof{proofs.data.length === 1 ? '' : 's'}
          {' · '}
          <span className="font-semibold text-success-text">{verified} verified</span>
        </p>
      )}

      {proofs.isPending && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading proofs">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex flex-col gap-4 rounded-2xl border p-5">
              <div className="flex gap-3">
                <Skeleton className="size-11 rounded-xl" />
                <div className="flex flex-1 flex-col gap-2">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              </div>
              <Skeleton className="h-6 w-24 rounded-full" />
              <Skeleton className="h-4 w-full" />
            </li>
          ))}
        </ul>
      )}
      {proofs.isError && <FormError message={apiErrorMessage(proofs.error)} />}
      {proofs.data?.length === 0 && (
        <Card className="px-5">
          <EmptyState
            icon={ShieldCheck}
            title="No proofs yet"
            description="Upload a licence, certificate, work sample, portfolio link, publication or reference. We review it the way an experienced professional in your field would, and tell you honestly how far it was verified."
            actions={
              <Button onClick={() => setAdding(true)}>
                <Plus /> Add your first proof
              </Button>
            }
          />
        </Card>
      )}
      {proofs.data && proofs.data.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {proofs.data.map((proof) => (
            <ProofCard key={proof.id} proof={proof} />
          ))}
        </ul>
      )}

      <details className="group rounded-2xl border bg-muted/40 p-4 text-sm">
        <summary className="cursor-pointer list-none font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/40">
          What the verification levels mean
        </summary>
        <dl className="mt-3 grid gap-3 sm:grid-cols-3">
          {Object.entries(LEVELS).map(([key, level]) => (
            <div key={key}>
              <dt className="flex items-center gap-1.5 font-medium">
                <level.icon className="size-4" aria-hidden /> {level.label}
              </dt>
              <dd className="text-muted-foreground">{level.meaning}</dd>
            </div>
          ))}
        </dl>
      </details>

      <Sheet open={adding} onOpenChange={setAdding}>
        <SheetContent className="w-full gap-0 overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-lg">
          <SheetHeader className="border-b">
            <SheetTitle>Add proof</SheetTitle>
            <SheetDescription>Show evidence for a skill. We check it and tell you honestly how far it was verified.</SheetDescription>
          </SheetHeader>
          <div className="p-4">
            <AddProofForm preselectSlug={params.get('skill')} preselectType={isProofType(type) ? type : null} bare />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
