import * as React from "react"
import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-20 w-full rounded-lg px-3 py-2 text-base leading-relaxed md:text-sm border border-input bg-card shadow-xs transition-[color,border-color,box-shadow] duration-150 outline-none placeholder:text-muted-foreground hover:border-[color-mix(in_oklch,var(--input),var(--foreground)_14%)] focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/20 disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-danger aria-invalid:ring-3 aria-invalid:ring-danger/15",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
