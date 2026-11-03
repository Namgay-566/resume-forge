/** Same-hue track + fill (dataviz meter spec). The value is always shown as text too. */
export function ProgressMeter({ value, max, label }: { value: number; max: number; label: string }) {
  const percent = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div
      className="h-2 overflow-hidden rounded-[4px] bg-primary/15"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-valuetext={`${value} of ${max}`}
    >
      <div className="h-full rounded-[4px] bg-primary transition-[width] duration-500" style={{ width: `${percent}%` }} />
    </div>
  )
}
