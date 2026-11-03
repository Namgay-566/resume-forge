import * as React from "react"
import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-lg px-3 py-1 text-base md:text-sm file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground border border-input bg-card shadow-xs transition-[color,border-color,box-shadow] duration-150 outline-none placeholder:text-muted-foreground hover:border-[color-mix(in_oklch,var(--input),var(--foreground)_14%)] focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/20 disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-danger aria-invalid:ring-3 aria-invalid:ring-danger/15",
        className
      )}
      {...props}
    />
  )
}

export { Input }
