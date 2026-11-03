import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleDot,
  ExternalLink,
  Info,
  Lightbulb,
  Loader2,
  MessageSquareQuote,
  PartyPopper,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  ThumbsUp,
  XCircle,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { GitHubMark } from '@/components/icons/github-mark'
import { ProgressRing } from '@/components/progress-ring'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { AnalysisProgress } from '@/features/proofs/analysis-progress'
import { useProof, useProofFileUrl, useReanalyze } from '@/features/proofs/api'
import { ProofBadge, proofTitle } from '@/features/proofs/proof-badge'
import { PROOF_TYPES } from '@/features/proofs/proof-types'
import { isRunning, type ProofCheck, type ProofDetail, type ProofStatus } from '@/features/proofs/types'
import { LEVELS } from '@/features/proofs/verification-level'
import { useResumes } from '@/features/resumes/api'
import { celebrate } from '@/lib/celebrate'
import { cn } from '@/lib/utils'
import { notifyError, notifySuccess } from '@/lib/notify'
import { useDocumentTitle } from '@/lib/use-document-title'

const VERDICT = {
  demonstrated: { label: 'Demonstrated', icon: CheckCircle2, badge: 'success', bar: 'bg-success' },
  partially: { label: 'Partially', icon: CircleDot, badge: 'warning', bar: 'bg-warning' },
  not_demonstrated: { label: 'Not demonstrated', icon: XCircle, badge: 'danger', bar: 'bg-danger' },
} as const
const CHECK_ICON = { pass: CheckCircle2, warn: AlertTriangle, fail: XCircle } as const
const CHECK_CLASS = { pass: 'text-success-text', warn: 'text-warning-text', fail: 'text-danger-text' } as const
const BANNER: Partial<Record<ProofStatus, { className: string; icon: typeof ShieldCheck; title: string }>> = {
  verified: { className: 'border-success/30 bg-success-muted', icon: ShieldCheck, title: 'Verified' },
  needs_more: { className: 'border-warning/40 bg-warning-muted', icon: AlertTriangle, title: 'Almost there' },
  rejected: { className: 'border-danger/30 bg-danger-muted', icon: ShieldAlert, title: 'Not accepted' },
}
const BANNER_TEXT: Partial<Record<ProofStatus, string>> = {
  verified: 'text-success-text',
  needs_more: 'text-warning-text',
  rejected: 'text-danger-text',
}

export function ProofDetailPage() {
  const { proofId = '' } = useParams()
  const proof = useProof(proofId)
  const rerun = useReanalyze(proofId)
  useDocumentTitle(proof.data ? proofTitle(proof.data) : null)
  const status = proof.data?.status
  // Celebrate when a proof turns verified while you're watching it (not on every visit).
  const previous = useRef(status)
  const [justVerified, setJustVerified] = useState(false)
  useEffect(() => {
    if (previous.current && isRunning(previous.current) && status === 'verified') {
      celebrate()
      setJustVerified(true)
    }
    previous.current = status
  }, [status])

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 self-start">
        <Link to="/proof-vault">
          <ArrowLeft /> Proof Vault
        </Link>
      </Button>

      {proof.isPending && (
        <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading proof">
          <Skeleton className="h-36 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-40 rounded-2xl" />
            <Skeleton className="h-40 rounded-2xl" />
          </div>
        </div>
      )}
      {proof.isError && <FormError message={apiErrorMessage(proof.error, { 404: 'Proof not found.' })} />}

      {proof.data && (
        <>
          <Header proof={proof.data} />
          {isRunning(proof.data.status) ? (
            <AnalysisProgress proof={proof.data} />
          ) : (
            <>
              {justVerified && <AddToResume proof={proof.data} onDismiss={() => setJustVerified(false)} />}
              <Verdict proof={proof.data} onRerun={() =>
                  rerun.mutate(undefined, {
                    onSuccess: () => notifySuccess('Analysis restarted', 'We’ll update this page as it runs.'),
                    onError: (err) => notifyError('Couldn’t restart the analysis', err),
                  })
                } rerunning={rerun.isPending} />
              {proof.data.report && <Report proof={proof.data} />}
            </>
          )}
        </>
      )}
    </div>
  )
}

function Header({ proof }: { proof: ProofDetail }) {
  const running = isRunning(proof.status)
  const Icon = proof.type === 'github_repo' ? GitHubMark : PROOF_TYPES[proof.type].icon
  const tone = proof.score === null ? '' : proof.score >= 70 ? 'var(--success)' : proof.score >= 50 ? 'var(--warning)' : 'var(--danger)'
  return (
    <Card variant="elevated" className="flex-col gap-5 px-5 py-5 sm:flex-row sm:items-center sm:px-6">
      <span className="flex size-14 shrink-0 items-center justify-center rounded-2xl border bg-muted/60">
        <Icon className="size-7" aria-hidden />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="min-w-0 truncate font-heading text-2xl font-semibold tracking-tight">{proofTitle(proof)}</h1>
          <ProofBadge proof={proof} />
        </div>
        {proof.url && (PROOF_TYPES[proof.type].input === 'link' || proof.type === 'professional_license') && (
          <a
            href={proof.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 self-start rounded-sm text-sm text-muted-foreground underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none"
          >
            {proof.url.replace(/^https?:\/\//, '')} <ExternalLink className="size-3.5" aria-label="opens in a new tab" />
          </a>
        )}
        <p className="flex flex-wrap gap-1.5">
          {proof.skills.map((s) => (
            <span key={s.id} className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
              {s.name}
            </span>
          ))}
        </p>
      </div>
      {proof.score !== null && !running && (
        <ProgressRing value={proof.score} color={tone} label="Review score" size={112} stroke={10} caption="review score" className="self-center" />
      )}
    </Card>
  )
}

function Verdict({ proof, onRerun, rerunning }: { proof: ProofDetail; onRerun: () => void; rerunning: boolean }) {
  const base = BANNER[proof.status]
  const level = proof.verification_level
  // The best this kind of proof can reach (a work sample or letter is always self-reported):
  // nothing is wrong, so it's information, not a warning, and re-running won't change it.
  const atCeiling = proof.status === 'needs_more' && level !== null && level === PROOF_TYPES[proof.type].ceiling
  const banner =
    base && proof.status === 'needs_more' && level
      ? { ...base, title: LEVELS[level].label, ...(atCeiling ? { className: 'border-info/30 bg-info-muted', icon: Info } : {}) }
      : base
  // Re-running helps unless every claimed skill is already demonstrated.
  const canImprove =
    !atCeiling && (proof.status !== 'verified' || (proof.report?.skills ?? []).some((s) => s.verdict !== 'demonstrated'))
  if (!banner) return null
  const Icon = banner.icon
  return (
    <section aria-label="Verdict" className={cn('flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center sm:p-5', banner.className)}>
      <Icon className={cn('size-6 shrink-0', atCeiling ? 'text-info-text' : BANNER_TEXT[proof.status])} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className={cn('font-heading font-semibold', atCeiling ? 'text-info-text' : BANNER_TEXT[proof.status])}>{banner.title}</p>
        {proof.decision && <p className="text-sm text-foreground">{proof.decision}</p>}
        {proof.verification_level && <p className="mt-1 text-xs text-muted-foreground">{LEVELS[proof.verification_level].meaning}</p>}
      </div>
      {canImprove && (
        <Button type="button" variant="outline" size="sm" className="self-start bg-card sm:self-center" onClick={onRerun} disabled={rerunning}>
          {rerunning ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          Re-run analysis
        </Button>
      )}
    </section>
  )
}

/** Shown right after a proof turns verified: put the skill on the resume while it's fresh. */
function AddToResume({ proof, onDismiss }: { proof: ProofDetail; onDismiss: () => void }) {
  const resumes = useResumes()
  const target = resumes.data?.[0]
  const demonstrated = (proof.report?.skills ?? []).filter((s) => s.verdict === 'demonstrated').map((s) => s.name)
  const skills = demonstrated.length ? demonstrated : proof.skills.map((s) => s.name)
  const names = skills.join(', ')
  return (
    <section
      aria-live="polite"
      aria-labelledby="add-to-resume-heading"
      className="relative isolate flex flex-col gap-4 overflow-hidden rounded-2xl border border-highlight/35 bg-highlight-muted p-5 shadow-sm sm:flex-row sm:items-center"
    >
      <div aria-hidden className="pointer-events-none absolute -top-14 -right-10 -z-10 size-48 rounded-full bg-highlight/25 blur-3xl" />
      <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-highlight text-highlight-foreground shadow-sm">
        <PartyPopper className="size-6" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <h2 id="add-to-resume-heading" className="text-h4">
          {names} {skills.length === 1 ? 'is' : 'are'} verified!
        </h2>
        <p className="text-sm text-muted-foreground">Add {skills.length === 1 ? 'it' : 'them'} to your resume with the proof link, so recruiters can click through.</p>
      </div>
      <div className="flex gap-2">
        <Button type="button" variant="ghost" onClick={onDismiss}>
          Not now
        </Button>
        <Button asChild variant="highlight">
          <Link to={target ? `/resumes/${target.id}` : '/resumes?new=1'}>
            <Sparkles /> Add to resume?
          </Link>
        </Button>
      </div>
    </section>
  )
}

function Report({ proof }: { proof: ProofDetail }) {
  const report = proof.report!
  const repo = report.repo
  const gates = report.checks.filter((c) => c.gate)
  const extras = report.checks.filter((c) => !c.gate)
  const reviewed = report.skills.length > 0 || report.summary

  return (
    <div className="flex flex-col gap-6">
      {report.certificate && <CertificatePanel proof={proof} />}
      {report.live && <LivePanel live={report.live} />}
      {report.license && <LicensePanel proof={proof} />}
      {report.portfolio && <PortfolioPanel info={report.portfolio} />}
      {report.publication && <PublicationPanel info={report.publication} />}
      {report.letter && <LetterPanel proof={proof} />}
      {proof.type === 'work_sample' && report.upload && (
        <Panel title="Work sample">
          {report.work_sample?.kind && <p className="text-sm">Reviewed as {report.work_sample.kind}.</p>}
          <FilePreview proof={proof} />
        </Panel>
      )}

      {report.ai_status !== 'ok' && report.ai_status !== 'skipped' && (
        <p className="rounded-xl bg-muted p-3 text-sm text-muted-foreground">
          The review couldn&apos;t run this time ({report.ai_status === 'unavailable' ? 'AI service unavailable' : 'review failed'}). Re-run the analysis
          later.
        </p>
      )}

      {report.summary && (
        <figure className="flex gap-4 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-secondary text-primary">
            <MessageSquareQuote className="size-5" aria-hidden />
          </span>
          <div className="flex flex-col gap-1.5">
            <figcaption className="eyebrow">{reviewerCaption(proof)}</figcaption>
            <blockquote className="font-heading text-lg leading-snug tracking-tight">“{report.summary}”</blockquote>
          </div>
        </figure>
      )}

      {report.skills.length > 0 && (
        <section aria-labelledby="skills-heading" className="flex flex-col gap-3">
          <h2 id="skills-heading" className="text-h4">
            Verdict per skill
          </h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {report.skills.map((s) => {
              const v = VERDICT[s.verdict]
              return (
                <li key={s.skill_id} className="relative flex flex-col gap-2 overflow-hidden rounded-xl border bg-card p-4 pl-5 shadow-xs">
                  <span aria-hidden className={cn('absolute inset-y-0 left-0 w-1', v.bar)} />
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold">{s.name}</p>
                    <Badge variant={v.badge}>
                      <v.icon /> {v.label}
                    </Badge>
                  </div>
                  {s.evidence.length > 0 && (
                    <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                      {s.evidence.map((e) => (
                        <li key={e} className="flex gap-2">
                          <span aria-hidden>·</span>
                          <span className="min-w-0 break-words">{e}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {reviewed && (
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="Strengths" icon={<ThumbsUp className="size-4 text-success-text" aria-hidden />}>
            {report.strengths?.length ? (
              <List items={report.strengths} icon={<CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success-text" aria-hidden />} />
            ) : (
              <p className="text-sm text-muted-foreground">The reviewer didn&apos;t single out strengths this time.</p>
            )}
          </Panel>
          <Panel title="Red flags" icon={<ShieldAlert className="size-4 text-danger-text" aria-hidden />} className={report.red_flags.length ? 'border-danger/30' : undefined}>
            {report.red_flags.length ? (
              <List items={report.red_flags} icon={<AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger-text" aria-hidden />} />
            ) : (
              <p className="flex items-center gap-2 text-sm text-success-text">
                <CheckCircle2 className="size-4" aria-hidden /> No red flags found.
              </p>
            )}
          </Panel>
        </div>
      )}

      {report.suggestions.length > 0 && (
        <section aria-labelledby="suggestions-heading" className="flex flex-col gap-3">
          <h2 id="suggestions-heading" className="flex items-center gap-2 text-h4">
            <Lightbulb className="size-4 text-highlight-text" aria-hidden /> How to make it stronger
          </h2>
          <ol className="grid gap-3 md:grid-cols-2">
            {report.suggestions.map((item, i) => (
              <li key={item} className="flex gap-3 rounded-xl border bg-card p-4 text-sm shadow-xs">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-highlight-muted text-xs font-semibold text-highlight-text">
                  {i + 1}
                </span>
                {item}
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {report.code_quality.length > 0 && (
          <Panel title={proof.type === 'github_repo' ? 'Code notes' : 'Notes'}>
            <List items={report.code_quality} />
          </Panel>
        )}
        {report.checks.length > 0 && (
          <Panel title="Requirements">
            <Checks checks={gates} />
            {extras.length > 0 && <Checks checks={extras} />}
          </Panel>
        )}
        {repo && (
          <Panel title="What we looked at">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-muted-foreground">Commits</dt>
              <dd>
                {repo.commit_count} on {repo.commit_days} day{repo.commit_days === 1 ? '' : 's'}
              </dd>
              <dt className="text-muted-foreground">Languages</dt>
              <dd>
                {Object.entries(repo.languages)
                  .slice(0, 4)
                  .map(([l, p]) => `${l} ${Math.round(p)}%`)
                  .join(', ') || 'n/a'}
              </dd>
              <dt className="text-muted-foreground">Tests · CI · Docker</dt>
              <dd>{[repo.has_tests, repo.has_ci, repo.has_docker].map((b) => (b ? 'yes' : 'no')).join(' · ')}</dd>
              {repo.fork && (
                <>
                  <dt className="text-muted-foreground">Fork of</dt>
                  <dd>
                    {repo.parent} ({repo.ahead_of_parent ?? '?'} own commits)
                  </dd>
                </>
              )}
            </dl>
            {(repo.key_files.length > 0 || repo.sampled_files.length > 0) && (
              <p className="mt-2 text-xs text-muted-foreground">Files reviewed: {[...repo.key_files, ...repo.sampled_files].join(', ')}</p>
            )}
          </Panel>
        )}
      </div>
      {report.error && <FormError message={report.error} />}
    </div>
  )
}

function Checks({ checks }: { checks: ProofCheck[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {checks.map((c) => {
        const Icon = CHECK_ICON[c.status]
        return (
          <li key={c.id} className="flex gap-2 text-sm">
            <Icon className={cn('mt-0.5 size-4 shrink-0', CHECK_CLASS[c.status])} aria-label={c.status} />
            <span>
              <span className="font-medium">{c.title}</span>
              <span className="block text-muted-foreground">{c.detail}</span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function List({ items, icon }: { items: string[]; icon?: React.ReactNode }) {
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          {icon ?? <span className="text-muted-foreground" aria-hidden>•</span>}
          {item}
        </li>
      ))}
    </ul>
  )
}

function Panel({ title, icon, children, className }: { title: string; icon?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn('flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs', className)}>
      <h2 className="flex items-center gap-2 text-h4">
        {icon}
        {title}
      </h2>
      {children}
    </section>
  )
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{value ?? <span className="text-muted-foreground">Not found</span>}</dd>
    </>
  )
}

function Tick({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  const Icon = ok ? CheckCircle2 : XCircle
  return (
    <li className="flex gap-2 text-sm">
      <Icon className={cn('mt-0.5 size-4 shrink-0', ok ? 'text-success-text' : 'text-muted-foreground')} aria-label={ok ? 'yes' : 'no'} />
      <span>{children}</span>
    </li>
  )
}

function CertificatePanel({ proof }: { proof: ProofDetail }) {
  const info = proof.report!.certificate!
  const check = info.url_check
  return (
    <Panel title="Certificate">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,16rem)]">
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <Fact label="Issuer" value={info.issuer} />
            <Fact label="Course" value={info.course_name} />
            <Fact label="Issued to" value={info.recipient_name} />
            <Fact label="Date" value={info.issue_date} />
            <Fact label="Credential ID" value={info.credential_id} />
            <Fact label="Verification link" value={info.verification_url} />
            <Fact label="Skills covered" value={info.mapped_skills.length ? info.mapped_skills.join(', ') : null} />
          </dl>
          <ul className="flex flex-col gap-1.5">
            {info.name_match && <Tick ok={info.name_match.status === 'match'}>{info.name_match.detail}</Tick>}
            {check ? (
              <>
                <Tick ok={check.reachable}>
                  Verification link {check.reachable ? 'is reachable' : `couldn't be checked: ${check.detail}`}
                </Tick>
                {check.reachable && (
                  <Tick ok={check.on_trusted_domain}>
                    {check.on_trusted_domain ? 'On the issuer’s site or a known credential platform' : 'Not on the issuer’s website'}
                  </Tick>
                )}
                {check.reachable && check.on_trusted_domain && (
                  <Tick ok={check.details_on_page}>
                    {check.details_on_page ? 'The page shows your name or credential ID' : 'The page doesn’t show your name or credential ID'}
                  </Tick>
                )}
              </>
            ) : (
              <Tick ok={false}>No verification link on the certificate</Tick>
            )}
            <Tick ok={info.text_source === 'pdf_text'}>
              {info.text_source === 'pdf_text'
                ? 'Read from the PDF’s text, so IDs and links were checked against the document'
                : 'Read from an image of the certificate'}
            </Tick>
          </ul>
        </div>
        <FilePreview proof={proof} />
      </div>
    </Panel>
  )
}

function LivePanel({ live }: { live: NonNullable<ProofDetail['report']>['live'] & object }) {
  return (
    <Panel title="Live site">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
        <Fact label="Title" value={live.title || null} />
        <Fact label="Description" value={live.description || null} />
        <Fact label="Final address" value={live.final_url} />
        <Fact label="Response" value={live.status_code ? `HTTP ${live.status_code}${live.response_ms ? ` in ${live.response_ms} ms` : ''}` : null} />
        <Fact label="Built from" value={live.linked_repo} />
      </dl>
      <ul className="flex flex-col gap-1.5">
        <Tick ok={live.reachable}>{live.reachable ? 'The site is up' : 'The site couldn’t be reached'}</Tick>
        {live.reachable && <Tick ok={live.https}>{live.https ? 'Served over HTTPS' : 'Not served over HTTPS'}</Tick>}
        {live.linked_repo && (
          <>
            <Tick ok={live.linked_repo_verified}>
              {live.linked_repo} {live.linked_repo_verified ? 'is verified' : 'isn’t verified yet'}
            </Tick>
            <Tick ok={Boolean(live.connection)}>{live.connection ?? 'Nothing ties the site to the repo yet'}</Tick>
          </>
        )}
      </ul>
    </Panel>
  )
}

function reviewerCaption(proof: ProofDetail): string {
  if (proof.type === 'github_repo') return 'Senior developer review'
  const who = proof.report?.reviewer
  return who ? `Reviewed as ${who}` : 'Review by an experienced professional in your field'
}

/** The uploaded file: an inline image, or a button to open it. */
function FilePreview({ proof }: { proof: ProofDetail }) {
  const upload = proof.report?.upload ?? proof.report?.certificate ?? null
  const file = useProofFileUrl(proof.id, Boolean(upload))
  if (!upload) return null
  const isImage = upload.content_type.startsWith('image/')
  const kind = isImage ? 'image' : upload.content_type === 'application/pdf' ? 'PDF' : 'document'
  return (
    <div className="flex flex-col gap-2">
      {file.data && isImage && <img src={file.data} alt={`${PROOF_TYPES[proof.type].label}: ${upload.filename}`} className="w-full rounded-lg border" />}
      {file.data && (
        <Button asChild variant="outline" size="sm" className="self-start">
          <a href={file.data} target="_blank" rel="noopener noreferrer" download={kind === 'document' ? upload.filename : undefined}>
            Open {kind}
          </a>
        </Button>
      )}
      {file.isError && <p className="text-xs text-muted-foreground">The file couldn't be loaded.</p>}
    </div>
  )
}

function LicensePanel({ proof }: { proof: ProofDetail }) {
  const info = proof.report!.license!
  const check = info.register_check
  return (
    <Panel title="Licence">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,16rem)]">
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <Fact label="Licence" value={info.license_type} />
            <Fact label="Issuing body" value={info.issuing_body} />
            <Fact label="Where" value={info.jurisdiction} />
            <Fact label="Holder" value={info.holder_name} />
            <Fact label="Number" value={info.license_number} />
            <Fact label="Issued" value={info.issue_date} />
            <Fact label="Expires" value={info.expiry_date} />
            <Fact label="Register link" value={info.register_url} />
            <Fact label="Skills covered" value={info.mapped_skills.length ? info.mapped_skills.join(', ') : null} />
          </dl>
          <ul className="flex flex-col gap-1.5">
            {info.name_match && <Tick ok={info.name_match.status === 'match'}>{info.name_match.detail}</Tick>}
            <Tick ok={!info.expired && !info.expires_soon && Boolean(info.expiry_date)}>{info.expiry_detail}</Tick>
            {check ? (
              <>
                <Tick ok={check.reachable}>Register link {check.reachable ? 'is reachable' : `couldn't be checked: ${check.detail}`}</Tick>
                {check.reachable && (
                  <Tick ok={check.on_trusted_domain}>
                    {check.on_trusted_domain ? 'On the licensing body’s site or a government domain' : 'Not on the licensing body’s website'}
                  </Tick>
                )}
                {check.reachable && check.on_trusted_domain && (
                  <Tick ok={check.details_on_page}>
                    {check.details_on_page ? 'The register shows your licence number or name' : 'The register page doesn’t show your number or name'}
                  </Tick>
                )}
              </>
            ) : (
              <Tick ok={false}>No link to the public register, so it couldn’t be checked independently</Tick>
            )}
          </ul>
        </div>
        <FilePreview proof={proof} />
      </div>
    </Panel>
  )
}

function PortfolioPanel({ info }: { info: NonNullable<NonNullable<ProofDetail['report']>['portfolio']> }) {
  return (
    <Panel title="Portfolio page">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
        <Fact label="Title" value={info.title || null} />
        <Fact label="Platform" value={info.platform ?? (info.site_name || null)} />
        <Fact label="Final address" value={info.final_url} />
      </dl>
      <ul className="flex flex-col gap-1.5">
        <Tick ok={info.reachable}>{info.reachable ? 'The page is public and loads' : 'The page couldn’t be reached'}</Tick>
        {info.reachable && <Tick ok={info.name_on_page}>{info.name_on_page ? 'Your name is on the page' : 'Your name isn’t on the page'}</Tick>}
        <Tick ok={false}>A public page can’t prove who made the work, so this is never fully verified</Tick>
      </ul>
    </Panel>
  )
}

function PublicationPanel({ info }: { info: NonNullable<NonNullable<ProofDetail['report']>['publication']> }) {
  return (
    <Panel title="Publication">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
        <Fact label="Title" value={info.title} />
        <Fact label="Published in" value={info.venue} />
        <Fact label="Date" value={info.published} />
        <Fact label="DOI" value={info.doi} />
        <Fact label="Authors" value={info.authors.length ? info.authors.join(', ') : null} />
      </dl>
      <ul className="flex flex-col gap-1.5">
        {info.doi && <Tick ok={info.registered}>{info.registered ? 'Found in the DOI registry' : 'Not found in the DOI registry'}</Tick>}
        {!info.doi && <Tick ok={false}>No DOI, so the publisher can’t be confirmed</Tick>}
        {info.author_match && <Tick ok={info.author_match.status === 'match'}>{info.author_match.detail}</Tick>}
      </ul>
    </Panel>
  )
}

function LetterPanel({ proof }: { proof: ProofDetail }) {
  const info = proof.report!.letter!
  return (
    <Panel title={proof.type === 'experience_letter' ? 'Experience letter' : 'Reference letter'}>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,16rem)]">
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <Fact label="Written by" value={[info.writer_name, info.writer_title].filter(Boolean).join(', ') || null} />
            <Fact label="Organisation" value={info.organization} />
            <Fact label="Relationship" value={info.relationship} />
            <Fact label="Date" value={info.date} />
            <Fact label="About" value={info.subject_name} />
          </dl>
          <ul className="flex flex-col gap-1.5">
            {info.name_match && <Tick ok={info.name_match.status === 'match'}>{info.name_match.detail}</Tick>}
            <Tick ok={info.has_contact_details}>
              {info.has_contact_details ? 'Includes the writer’s contact details' : 'No contact details for the writer'}
            </Tick>
            <Tick ok={false}>We can’t contact the writer, so letters are always self-reported</Tick>
          </ul>
          {info.skills_mentioned.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">Skills it mentions</h3>
              <ul className="flex flex-col gap-2">
                {info.skills_mentioned.map((m) => (
                  <li key={m.name} className="text-sm">
                    <span className="font-medium">{m.name}</span>
                    <span className="block text-muted-foreground">“{m.quote}”</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <FilePreview proof={proof} />
      </div>
    </Panel>
  )
}

