import { toast } from 'sonner'

import { apiErrorMessage } from '@/features/auth/api-error'

/** Success toast. Keep messages short and human: "Resume duplicated". */
export function notifySuccess(message: string, description?: string) {
  toast.success(message, { description })
}

/** Error toast with a friendly explanation (never raw server or stack text).
 * `byStatus` overrides the message for specific HTTP statuses. */
export function notifyError(title: string, error: unknown, byStatus: Record<number, string> = {}) {
  toast.error(title, { description: apiErrorMessage(error, byStatus) })
}
