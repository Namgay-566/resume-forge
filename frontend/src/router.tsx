import { createBrowserRouter } from 'react-router'

import { AppLayout } from '@/layouts/app-layout'
import { DashboardPage } from '@/pages/dashboard-page'
import { LandingPage } from '@/pages/landing-page'
import { PlaceholderPage } from '@/pages/placeholder-page'

export const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  {
    path: '/app',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'resumes', element: <PlaceholderPage title="My Resumes" /> },
      { path: 'skill-gap', element: <PlaceholderPage title="Skill Gap" /> },
      { path: 'proof-vault', element: <PlaceholderPage title="Proof Vault" /> },
      { path: 'settings', element: <PlaceholderPage title="Settings" /> },
    ],
  },
])
