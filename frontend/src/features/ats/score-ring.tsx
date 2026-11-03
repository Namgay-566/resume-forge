import { AlertOctagon, AlertTriangle, CheckCircle2, type LucideIcon } from 'lucide-react'

// Status palette (dataviz skill): good / warning / critical. Never color alone: every band
// ships with an icon and a word, and the number itself stays in the text color.
const BANDS: { min: number; label: string; color: string; icon: LucideIcon }[] = [
  { min: 80, label: 'Strong', color: '#0ca30c', icon: CheckCircle2 },
  { min: 60, label: 'Needs work', color: '#fab219', icon: AlertTriangle },
  { min: 0, label: 'At risk', color: '#d03b3b', icon: AlertOctagon },
]

export function scoreBand(score: number) {
  return BANDS.find((band) => score >= band.min) ?? BANDS[BANDS.length - 1]
}

const SIZE = 136
const STROKE = 10
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

interface ScoreRingProps {
  score: number
  /** What the number is, for screen readers, e.g. "ATS score". */
  title?: string
  /** Band words from high to low, replacing Strong / Needs work / At risk. */
  labels?: [string, string, string]
}

/** Circular meter: same-hue track, rounded data end, hero number in the middle. */
export function ScoreRing({ score, title = 'ATS score', labels }: ScoreRingProps) {
  const base = scoreBand(score)
  const band = labels ? { ...base, label: labels[BANDS.indexOf(base)] } : base
  const Icon = band.icon
  const filled = (Math.max(0, Math.min(100, score)) / 100) * CIRCUMFERENCE

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="relative"
        style={{ width: SIZE, height: SIZE }}
        role="img"
        aria-label={`${title} ${score} out of 100: ${band.label}`}
      >
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90">
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={band.color}
            strokeOpacity={0.18}
            strokeWidth={STROKE}
          />
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={band.color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${CIRCUMFERENCE}`}
            className="transition-[stroke-dasharray] duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden>
          <span className="text-5xl leading-none font-semibold">{score}</span>
          <span className="mt-1 text-xs text-muted-foreground">out of 100</span>
        </div>
      </div>
      <p className="flex items-center gap-1.5 text-sm font-medium">
        <Icon className="size-4" style={{ color: band.color }} aria-hidden />
        {band.label}
      </p>
    </div>
  )
}
