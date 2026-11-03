import { isAxiosError } from 'axios'

interface Options {
  /** Show the server's own `detail` message (for endpoints whose errors are user-facing). */
  useServerDetail?: boolean
}

export function apiErrorMessage(
  error: unknown,
  byStatus: Record<number, string> = {},
  { useServerDetail = false }: Options = {},
): string {
  if (isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') return 'Cancelled.'
    if (!error.response) return 'Cannot reach the server. Check your connection and try again.'
    const custom = byStatus[error.response.status]
    if (custom) return custom
    const detail = (error.response.data as { detail?: unknown } | undefined)?.detail
    if (useServerDetail && typeof detail === 'string') return detail
  }
  return 'Something went wrong. Please try again.'
}
