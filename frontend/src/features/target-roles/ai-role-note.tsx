import { Sparkles } from 'lucide-react'

import { cn } from '@/lib/utils'

/** Says plainly that a role's required skills were drafted by AI, not curated. */
export function AiRoleNote({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <p className={cn('flex items-start gap-1.5 text-xs text-info-text', className)}>
      <Sparkles className="mt-px size-3.5 shrink-0" aria-hidden />
      <span>
        <span className="font-medium">AI-generated role.</span>{' '}
        {compact
          ? 'Its required skills were drafted by AI from the job title.'
          : 'Its required skills were drafted by AI from the job title, so check them against a real job advert.'}
      </span>
    </p>
  )
}
