import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: ReactNode
  /** Buttons or links. The first should be the obvious next step. */
  actions?: ReactNode
  size?: 'sm' | 'md'
  className?: string
}

/** Friendly "nothing here yet": a soft illustrated icon, one sentence, one clear action. */
export function EmptyState({ icon: Icon, title, description, actions, size = 'md', className }: EmptyStateProps) {
  const small = size === 'sm'
  return (
    <div className={cn('flex flex-col items-center text-center', small ? 'gap-3 py-6' : 'gap-4 py-10', className)}>
      <div aria-hidden className={cn('relative flex items-center justify-center', small ? 'size-16' : 'size-24')}>
        <span className="absolute inset-0 rounded-full bg-gradient-to-br from-secondary to-highlight-muted" />
        <span className={cn('absolute rounded-full border border-dashed border-primary/25', small ? '-inset-1.5' : '-inset-3')} />
        <span
          className={cn(
            'relative flex items-center justify-center rounded-2xl border bg-card text-primary shadow-md',
            small ? 'size-9 rotate-[-6deg]' : 'size-12 rotate-[-6deg]',
          )}
        >
          <Icon className={small ? 'size-4' : 'size-6'} />
        </span>
      </div>
      <div className="flex max-w-sm flex-col gap-1">
        <p className={cn('font-heading font-semibold tracking-tight', small ? 'text-base' : 'text-lg')}>{title}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap justify-center gap-2 pt-1">{actions}</div>}
    </div>
  )
}
