import { CircleAlert, CircleCheck, Info, LoaderCircle, TriangleAlert } from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

import { useTheme } from "@/features/theme/use-theme"

/** Toasts, themed with the design tokens. Use `toast.success()` for verified or saved,
 * `toast.warning()` for needs-attention, `toast.error()` for failures. */
function Toaster(props: ToasterProps) {
  const { resolved } = useTheme()
  return (
    <Sonner
      theme={resolved}
      position="bottom-right"
      className="toaster group"
      icons={{
        success: <CircleCheck className="size-4 text-success-text" />,
        info: <Info className="size-4 text-primary" />,
        warning: <TriangleAlert className="size-4 text-warning-text" />,
        error: <CircleAlert className="size-4 text-danger-text" />,
        loading: <LoaderCircle className="size-4 animate-spin text-muted-foreground" />,
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast !gap-3 !rounded-xl !border !border-border !bg-popover !p-4 !font-sans !text-popover-foreground !shadow-lg",
          title: "!text-sm !font-semibold",
          description: "!text-sm !text-muted-foreground",
          actionButton: "!rounded-md !bg-primary !text-primary-foreground !font-medium",
          cancelButton: "!rounded-md !bg-muted !text-muted-foreground",
          closeButton: "!border-border !bg-popover !text-muted-foreground",
          success: "!border-success/30",
          warning: "!border-warning/40",
          error: "!border-danger/30",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
