import { FileText, LayoutDashboard, Map as MapIcon, Settings, ShieldCheck, Target, type LucideIcon } from 'lucide-react'
import { matchPath } from 'react-router'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Workspace',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/resumes', label: 'My Resumes', icon: FileText },
    ],
  },
  {
    label: 'Grow',
    items: [
      { to: '/skill-gap', label: 'Skill Gap', icon: Target },
      { to: '/roadmap', label: 'Roadmap', icon: MapIcon },
      { to: '/proof-vault', label: 'Proof Vault', icon: ShieldCheck },
    ],
  },
]

export const SETTINGS_ITEM: NavItem = { to: '/settings', label: 'Settings', icon: Settings }

// Most specific first.
const TITLES: [string, string][] = [
  ['/resumes/:resumeId', 'Resume editor'],
  ['/proof-vault/:proofId', 'Proof details'],
  ['/dashboard', 'Dashboard'],
  ['/resumes', 'My Resumes'],
  ['/skill-gap', 'Skill Gap'],
  ['/roadmap', 'Roadmap'],
  ['/proof-vault', 'Proof Vault'],
  ['/settings', 'Settings'],
]

export function pageTitle(pathname: string): string {
  return TITLES.find(([pattern]) => matchPath(pattern, pathname))?.[1] ?? 'ResumeForge'
}
