import { cn } from "@/lib/utils"

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? "?").slice(0, 2)
  return letters.toUpperCase()
}

/** Initials in a brand-tinted circle. Decorative: pair it with the name in text. */
function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 font-heading text-xs font-semibold text-white ring-2 ring-background select-none",
        className
      )}
    >
      {initials(name)}
    </span>
  )
}

export { Avatar }
