import { BookOpen, Upload } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { proofAction, proofHint, proofLink } from './links'
import { STATUS, StatusBadge } from './status-badge'
import type { RoleSkillGap } from './types'

const TONE = {
  success: { bar: 'bg-success', tile: 'bg-success-muted text-success-text' },
  warning: { bar: 'bg-warning', tile: 'bg-warning-muted text-warning-text' },
  info: { bar: 'bg-info', tile: 'bg-info-muted text-info-text' },
  danger: { bar: 'bg-danger', tile: 'bg-danger-muted text-danger-text' },
} as const

function evidenceText(skill: RoleSkillGap): string | null {
  if (skill.status === 'missing') return null
  const first = skill.evidence[0]
  if (!first) return null
  if (first.kind === 'ai_inferred' || first.kind === 'resume_text') return `“${first.detail}”`
  return skill.evidence.map((e) => e.detail).join(' · ')
}

interface SkillCardProps {
  skill: RoleSkillGap
  /** The skill's group, or its importance when the page is grouped by category. */
  subtitle: string
  resumeId: string
  onLearn: (skill: RoleSkillGap) => void
}

/** One role skill, colour-coded by status (always with an icon and a word too). */
export function SkillCard({ skill, subtitle, resumeId, onLearn }: SkillCardProps) {
  const status = STATUS[skill.status]
  const tone = TONE[status.tone]
  const Icon = status.icon
  const evidence = evidenceText(skill)
  const pending = skill.verification_status === 'pending'

  return (
    <li className="relative flex flex-col gap-3 overflow-hidden rounded-xl border bg-card p-4 pl-5 shadow-xs">
      <span aria-hidden className={cn('absolute inset-y-0 left-0 w-1', tone.bar)} />
      <div className="flex items-start gap-3">
        <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', tone.tile)}>
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-snug break-words">{skill.name}</p>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        <StatusBadge status={skill.status} />
      </div>
      <p className="text-sm text-muted-foreground">
        {evidence ?? status.hint}
        {skill.status === 'inferred' && ' Add it to your Skills section if it’s true.'}
      </p>
      {skill.status !== 'present_verified' && proofHint(skill) && <p className="-mt-1 text-xs text-muted-foreground">{proofHint(skill)}</p>}
      {skill.status !== 'present_verified' && (
        <div className="mt-auto flex flex-wrap gap-1.5">
          {skill.status !== 'present_unverified' && (
            <Button type="button" size="sm" variant="ghost" onClick={() => onLearn(skill)}>
              <BookOpen /> Learn it
            </Button>
          )}
          {pending ? (
            <span className="self-center px-2 text-xs font-medium text-info-text">Proof under review</span>
          ) : (
            <Button asChild size="sm" variant="ghost">
              <Link to={proofLink(skill, resumeId)}>
                <Upload /> {proofAction(skill)}
              </Link>
            </Button>
          )}
        </div>
      )}
    </li>
  )
}
