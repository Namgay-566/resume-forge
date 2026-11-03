import { ShieldCheck, ShieldHalf, UserPen, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { VerificationLevel } from './types'

export const LEVELS: Record<VerificationLevel, { label: string; icon: LucideIcon; className: string; meaning: string }> = {
  verified: {
    label: 'Verified',
    icon: ShieldCheck,
    className: 'border-success/25 bg-success-muted text-success-text',
    meaning: 'Independently confirmed by a source we could check: the licensing body’s public register, the issuer’s own site, the DOI registry, or your own code on GitHub.',
  },
  partially_verified: {
    label: 'Partially verified',
    icon: ShieldHalf,
    className: 'border-warning/40 bg-warning-muted text-warning-text',
    meaning: 'Some checks passed, but not everything could be confirmed.',
  },
  self_reported: {
    label: 'Self-reported',
    icon: UserPen,
    className: 'border-border bg-muted text-muted-foreground',
    meaning: 'Recorded as you submitted it. There was no way to confirm it independently.',
  },
}

export function VerificationBadge({ level }: { level: VerificationLevel }) {
  const { label, icon: Icon, className } = LEVELS[level]
  return (
    <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-full border px-2.5 text-xs font-medium', className)}>
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  )
}
