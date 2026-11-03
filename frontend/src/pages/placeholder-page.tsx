import { Construction } from 'lucide-react'

import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { Card } from '@/components/ui/card'

interface PlaceholderPageProps {
  title: string
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <PageHeader title={title} />
      <Card className="px-5">
        <EmptyState icon={Construction} title="Coming soon" description="This page isn’t built yet." />
      </Card>
    </div>
  )
}
