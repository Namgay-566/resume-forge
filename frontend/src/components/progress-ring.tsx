import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { useCountUp } from '@/lib/use-count-up'

interface ProgressRingProps {
  /** 0-100, or null for "no value yet" (an empty track). */
  value: number | null
  /** CSS color for the arc, e.g. "var(--series-ats)". */
  color: string
  size?: number
  stroke?: number
  /** Accessible name, e.g. "ATS score". */
  label: string
  /** Text under the number inside the ring. */
  caption?: ReactNode
  className?: string
}

/** Animated circular progress: the arc and the number count up together, once, on view. */
export function ProgressRing({ value, color, size = 152, stroke = 12, label, caption, className }: ProgressRingProps) {
  const { ref, current } = useCountUp(value ?? 0)
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const shown = value === null ? 0 : current

  return (
    <div
      ref={ref}
      // A meter needs a value; with none yet it's an image that says so.
      {...(value === null
        ? { role: 'img', 'aria-label': `${label}: not measured yet` }
        : {
            role: 'meter',
            'aria-label': label,
            'aria-valuemin': 0,
            'aria-valuemax': 100,
            'aria-valuenow': value,
            'aria-valuetext': `${value} out of 100`,
          })}
      className={cn('relative shrink-0', className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-muted" />
        {value !== null && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            stroke={color}
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - shown / 100)}
            style={{ filter: `drop-shadow(0 2px 6px color-mix(in oklch, ${color} 35%, transparent))` }}
          />
        )}
      </svg>
      <div aria-hidden className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-heading leading-none font-semibold tracking-tight tabular-nums" style={{ fontSize: size * 0.28 }}>
          {value === null ? '–' : shown}
          {value !== null && caption === undefined && <span className="text-[0.4em] text-muted-foreground">%</span>}
        </span>
        {caption && <span className="mt-1.5 text-xs font-medium text-muted-foreground">{caption}</span>}
      </div>
    </div>
  )
}
