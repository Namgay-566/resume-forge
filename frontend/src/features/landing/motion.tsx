import { domAnimation, LazyMotion, m, MotionConfig } from 'framer-motion'
import type { ReactNode } from 'react'

import { useCountUp } from '@/lib/use-count-up'

import { cn } from '@/lib/utils'

const EASE = [0.22, 1, 0.36, 1] as const

/** Wraps the page: small motion bundle (domAnimation only) and respects "reduce motion". */
export function LandingMotion({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user" transition={{ duration: 0.55, ease: EASE }}>
        {children}
      </MotionConfig>
    </LazyMotion>
  )
}

interface RevealProps {
  children: ReactNode
  className?: string
  delay?: number
  /** Slide distance in px. */
  y?: number
  as?: 'div' | 'li' | 'section'
}

/** Fade and slide up once, when scrolled into view. */
export function Reveal({ children, className, delay = 0, y = 18, as = 'div' }: RevealProps) {
  const Tag = m[as]
  return (
    <Tag
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.55, ease: EASE, delay }}
    >
      {children}
    </Tag>
  )
}

export function ScoreRing({ value, size = 132, label = 'ATS score', className }: { value: number; size?: number; label?: string; className?: string }) {
  const { ref, current } = useCountUp(value)
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <div ref={ref} className={cn('relative shrink-0', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-muted" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          stroke="url(#rf-ring)"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - current / 100)}
        />
        <defs>
          <linearGradient id="rf-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--color-brand-500)" />
            <stop offset="100%" stopColor="var(--success)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-heading text-4xl leading-none font-semibold tabular-nums" aria-hidden>
          {current}
        </span>
        <span className="mt-1 text-[11px] font-medium text-muted-foreground">{label}</span>
      </div>
      <span className="sr-only">
        {label}: {value} out of 100
      </span>
    </div>
  )
}
