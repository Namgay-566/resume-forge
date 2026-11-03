import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { Reveal } from './motion'

export function SectionHeading({
  eyebrow,
  title,
  children,
  align = 'center',
  className,
}: {
  eyebrow: string
  title: ReactNode
  children?: ReactNode
  align?: 'center' | 'left'
  className?: string
}) {
  return (
    <Reveal className={cn('flex max-w-2xl flex-col gap-3', align === 'center' && 'mx-auto items-center text-center', className)}>
      <p className="eyebrow text-primary">{eyebrow}</p>
      <h2 className="text-[2rem] leading-[1.15] font-[650] tracking-[-0.03em] md:text-h1">{title}</h2>
      {children && <p className="text-base text-muted-foreground md:text-lg">{children}</p>}
    </Reveal>
  )
}
