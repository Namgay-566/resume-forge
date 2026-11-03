import { Loader2 } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'

import { Button } from '@/components/ui/button'

interface SubmitButtonProps extends Omit<ComponentProps<typeof Button>, 'type'> {
  pending: boolean
  /** Label while working, e.g. "Saving…". */
  pendingText: ReactNode
}

/** Submit button that disables itself and shows a spinner while the action runs. */
export function SubmitButton({ pending, pendingText, children, disabled, ...props }: SubmitButtonProps) {
  return (
    <Button type="submit" disabled={pending || disabled} aria-busy={pending || undefined} {...props}>
      {pending && <Loader2 className="animate-spin" aria-hidden />}
      {pending ? pendingText : children}
    </Button>
  )
}
