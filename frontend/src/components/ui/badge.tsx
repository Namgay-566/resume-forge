import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { Slot } from "radix-ui"

const badgeVariants = cva(
  "group/badge inline-flex h-6 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border px-2.5 text-xs font-medium whitespace-nowrap transition-colors focus-visible:ring-3 focus-visible:ring-ring/40 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&>svg]:pointer-events-none [&>svg]:size-3.5!",
  {
    variants: {
      variant: {
        // Brand-tinted label (roles, tags).
        default: "border-transparent bg-secondary text-secondary-foreground [a]:hover:bg-accent",
        // Neutral metadata ("Resume", "CV", "Checking...").
        secondary: "border-transparent bg-muted text-muted-foreground [a]:hover:text-foreground",
        solid: "border-transparent bg-primary text-primary-foreground [a]:hover:bg-primary-hover",
        outline: "border-border text-foreground [a]:hover:bg-muted",
        // Status. Always pair with an icon or a word, never color alone.
        success: "border-success/25 bg-success-muted text-success-text",
        warning: "border-warning/40 bg-warning-muted text-warning-text",
        danger: "border-danger/25 bg-danger-muted text-danger-text",
        info: "border-info/25 bg-info-muted text-info-text",
        destructive: "border-danger/25 bg-danger-muted text-danger-text",
        // Encouraging emphasis ("New", "Almost there").
        highlight: "border-highlight/30 bg-highlight-muted text-highlight-text",
        ghost: "border-transparent hover:bg-muted",
        link: "border-transparent text-primary underline-offset-4 hover:underline",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
