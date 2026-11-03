import type { ReactNode } from 'react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface SettingsSectionProps {
  id: string
  title: string
  description?: ReactNode
  children: ReactNode
  /** The danger zone: red border and heading. */
  danger?: boolean
}

/** One card on the Settings page. The id is the in-page anchor (/settings#security). */
export function SettingsSection({ id, title, description, children, danger = false }: SettingsSectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20">
      <Card className={cn('gap-0 px-5 py-0', danger && 'border-danger/40')}>
        <header className="flex flex-col gap-1 border-b py-4">
          <h2 id={`${id}-title`} className={cn('font-heading text-base font-semibold', danger && 'text-danger-text')}>
            {title}
          </h2>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </header>
        <div className="@container flex flex-col divide-y">{children}</div>
      </Card>
    </section>
  )
}

interface SettingRowProps {
  label: ReactNode
  hint?: ReactNode
  /** The control: a select, a button, a switch. */
  children: ReactNode
  htmlFor?: string
  className?: string
}

/** A label and hint on the left, the control on the right; stacked when the card is narrow. */
export function SettingRow({ label, hint, children, htmlFor, className }: SettingRowProps) {
  return (
    <div className={cn('flex flex-col gap-3 py-4 @xl:flex-row @xl:items-center @xl:justify-between @xl:gap-6', className)}>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="text-sm font-medium">
            {label}
          </label>
        ) : (
          <span className="text-sm font-medium">{label}</span>
        )}
        {hint && <span className="text-sm text-muted-foreground">{hint}</span>}
      </div>
      <div className="flex min-w-0 shrink-0 flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}
