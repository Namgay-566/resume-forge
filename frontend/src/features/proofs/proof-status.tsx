import { AlertTriangle, CircleX, Clock, Loader2, ShieldCheck, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { ProofStatus } from './types'

// Icon + word on every badge: status never relies on colour alone.
const STATUS: Record<ProofStatus, { label: string; icon: LucideIcon; className: string; spin?: boolean }> = {
  pending: { label: 'Queued', icon: Clock, className: 'border-border bg-muted text-muted-foreground' },
  analyzing: { label: 'Analyzing', icon: Loader2, className: 'border-info/25 bg-info-muted text-info-text', spin: true },
  verified: { label: 'Verified', icon: ShieldCheck, className: 'border-success/25 bg-success-muted text-success-text' },
  needs_more: { label: 'Needs more', icon: AlertTriangle, className: 'border-warning/40 bg-warning-muted text-warning-text' },
  rejected: { label: 'Rejected', icon: CircleX, className: 'border-danger/25 bg-danger-muted text-danger-text' },
}

export function ProofStatusBadge({ status }: { status: ProofStatus }) {
  const { label, icon: Icon, className, spin } = STATUS[status]
  return (
    <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-full border px-2.5 text-xs font-medium', className)}>
      <Icon className={cn('size-3.5', spin && 'animate-spin')} aria-hidden />
      {label}
    </span>
  )
}
