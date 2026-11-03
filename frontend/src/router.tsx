import { createBrowserRouter, Navigate } from 'react-router'

import { RedirectIfAuthenticated, RequireAuth } from '@/features/auth/route-guards'
import { AppLayout } from '@/layouts/app-layout'
import { DashboardPage } from '@/pages/dashboard-page'
import { LandingPage } from '@/pages/landing-page'
import { LoginPage } from '@/pages/login-page'
import { ProofDetailPage } from '@/pages/proof-detail-page'
import { ProofVaultPage } from '@/pages/proof-vault-page'
import { RegisterPage } from '@/pages/register-page'
import { ResumeEditorPage } from '@/pages/resume-editor-page'
import { ResumesPage } from '@/pages/resumes-page'
import { RoadmapPage } from '@/pages/roadmap-page'
import { SettingsPage } from '@/pages/settings-page'
import { SkillGapPage } from '@/pages/skill-gap-page'

export const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  {
    element: <RedirectIfAuthenticated />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/dashboard', element: <DashboardPage /> },
          { path: '/resumes', element: <ResumesPage /> },
          { path: '/resumes/:resumeId', element: <ResumeEditorPage /> },
          { path: '/skill-gap', element: <SkillGapPage /> },
          { path: '/roadmap', element: <RoadmapPage /> },
          { path: '/proof-vault', element: <ProofVaultPage /> },
          { path: '/proof-vault/:proofId', element: <ProofDetailPage /> },
          { path: '/settings', element: <SettingsPage /> },
        ],
      },
    ],
  },
  // Dev-only design reference. The check is a build-time constant, so production bundles
  // contain neither the route nor the page.
  ...(import.meta.env.DEV
    ? [
        {
          path: '/design-system',
          lazy: async () => ({ Component: (await import('@/pages/design-system-page')).DesignSystemPage }),
        },
      ]
    : []),
  // Old /app links from the first scaffold.
  { path: '/app/*', element: <Navigate to="/dashboard" replace /> },
])
