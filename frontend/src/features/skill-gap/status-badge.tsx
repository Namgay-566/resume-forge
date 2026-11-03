import { CircleAlert, CircleX, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

import type { SkillStatus } from './types'

// Icon + word on every badge: status never relies on colour alone.
// tone drives the card accents on the Skill Gap page: verified green, unverified amber,
// inferred blue, missing red.
export const STATUS: Record<SkillStatus, { label: string; icon: LucideIcon; className: string; tone: 'success' | 'warning' | 'info' | 'danger'; hint: string }> = {
  present_verified: { label: 'Verified', icon: ShieldCheck, className: 'border-success/25 bg-success-muted text-success-text', tone: 'success', hint: 'Backed by a checked proof' },
  present_unverified: { label: 'Unverified', icon: CircleAlert, className: 'border-warning/40 bg-warning-muted text-warning-text', tone: 'warning', hint: 'On your resume, not proven yet' },
  inferred: { label: 'Inferred', icon: Sparkles, className: 'border-info/25 bg-info-muted text-info-text', tone: 'info', hint: 'Implied by your experience' },
  missing: { label: 'Missing', icon: CircleX, className: 'border-danger/25 bg-danger-muted text-danger-text', tone: 'danger', hint: 'Not on your resume' },
}

export function StatusBadge({ status }: { status: SkillStatus }) {
  const { label, icon: Icon, className } = STATUS[status]
  return (
    <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-full border px-2.5 text-xs font-medium', className)}>
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  )
}
