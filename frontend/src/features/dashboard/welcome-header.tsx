import { Skeleton } from '@/components/ui/skeleton'

import { firstName, greeting } from './status'

export function WelcomeHeader({ name, status }: { name?: string; status: string | null }) {
  const first = firstName(name)
  return (
    <div className="flex flex-col gap-1.5">
      <h1 className="text-[1.75rem] leading-tight font-[650] tracking-[-0.025em] md:text-h1">
        {greeting()}
        {first && `, ${first}`}
      </h1>
      {status === null ? <Skeleton className="h-5 w-72 max-w-full" /> : <p className="text-base text-muted-foreground md:text-lg">{status}</p>}
    </div>
  )
}
