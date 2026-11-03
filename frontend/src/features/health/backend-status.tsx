import { Badge } from '@/components/ui/badge'

import { useHealth } from './use-health'

export function BackendStatus() {
  const { data, isPending, isError } = useHealth()

  if (isPending) return <Badge variant="secondary">Checking backend…</Badge>
  if (isError || data.status !== 'ok') {
    return <Badge variant="destructive">Backend unreachable</Badge>
  }
  return <Badge variant="success">Backend connected</Badge>
}
