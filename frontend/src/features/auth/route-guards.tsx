import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router'

import { safeNextPath } from './next-path'
import { useAuth } from './use-auth'

function FullPageSpinner() {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
    </div>
  )
}

/** Only signed-in users; everyone else goes to /login and comes back afterwards. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <FullPageSpinner />
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}

/** Login/register: signed-in users go where they were headed (?next= or the page that sent
 * them to log in), else the dashboard. This also runs right after a successful sign-in, so
 * it must honour the same destination the form does. */
export function RedirectIfAuthenticated() {
  const { status } = useAuth()
  const location = useLocation()
  const [params] = useSearchParams()

  if (status === 'loading') return <FullPageSpinner />
  if (status === 'authenticated') {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={safeNextPath(params.get('next'), from) ?? '/dashboard'} replace />
  }
  return <Outlet />
}
