import { useEffect } from 'react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { PageHeader } from '@/components/page-header'
import { useAuth } from '@/features/auth/use-auth'
import { DangerZone, DataSection } from '@/features/settings/data-section'
import { connectErrorMessage, providerLabel } from '@/features/settings/helpers'
import { AppearanceSection, NotificationsSection } from '@/features/settings/preferences-sections'
import { ProfileSection } from '@/features/settings/profile-section'
import { ResumeDefaultsSection } from '@/features/settings/resume-defaults-section'
import { SecuritySection } from '@/features/settings/security-section'

const SECTIONS = [
  { id: 'profile', label: 'Profile' },
  { id: 'security', label: 'Sign-in and security' },
  { id: 'resume-defaults', label: 'Resume defaults' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'data', label: 'Your data' },
  { id: 'delete', label: 'Delete account' },
]

/** Toast the result of connecting an account, then drop it from the URL. */
function useConnectResult() {
  const [params, setParams] = useSearchParams()
  const connected = params.get('connected')
  const error = params.get('connect_error')

  useEffect(() => {
    if (!connected && !error) return
    if (connected) toast.success(`${providerLabel(connected)} connected`)
    if (error) toast.error(connectErrorMessage(error))
    setParams({}, { replace: true })
  }, [connected, error, setParams])
}

export function SettingsPage() {
  const { user } = useAuth()
  useConnectResult()
  if (!user) return null

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title="Settings" description="Your account, how your resumes start, and your data." />
      <div className="grid gap-8 lg:grid-cols-[12rem_1fr]">
        <nav aria-label="Settings sections" className="hidden lg:block">
          <ul className="sticky top-20 flex flex-col gap-0.5 text-sm">
            {SECTIONS.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="block rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {section.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex min-w-0 flex-col gap-6">
          <ProfileSection user={user} />
          <SecuritySection user={user} />
          <ResumeDefaultsSection user={user} />
          <NotificationsSection user={user} />
          <AppearanceSection />
          <DataSection />
          <DangerZone user={user} />
        </div>
      </div>
    </div>
  )
}
