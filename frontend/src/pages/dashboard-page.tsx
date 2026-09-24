import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { BackendStatus } from '@/features/health/backend-status'

export function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>Connection to the ResumeForge API.</CardDescription>
        </CardHeader>
        <CardContent>
          <BackendStatus />
        </CardContent>
      </Card>
    </div>
  )
}
