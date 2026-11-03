import { cn } from '@/lib/utils'

/** "+6" / "-2" / "±0", in text tokens with a soft tint (never color alone: the sign carries it). */
export function Delta({ value }: { value: number }) {
  return (
    <span
      className={cn(
        'rounded px-1 text-xs font-medium tabular-nums',
        value > 0
          ? 'bg-success-muted text-success-text'
          : value < 0
            ? 'bg-danger-muted text-danger-text'
            : 'bg-muted',
      )}
    >
      {value > 0 ? `+${value}` : value === 0 ? '±0' : value}
    </span>
  )
}
