import {
  FileText,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  Target,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router'

import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

const navItems: NavItem[] = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/app/resumes', label: 'My Resumes', icon: FileText },
  { to: '/app/skill-gap', label: 'Skill Gap', icon: Target },
  { to: '/app/proof-vault', label: 'Proof Vault', icon: ShieldCheck },
  { to: '/app/settings', label: 'Settings', icon: Settings },
]

function NavLinks({ className }: { className?: string }) {
  return (
    <nav className={className}>
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/app'}
          className={({ isActive }) =>
            cn(
              'flex shrink-0 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppLayout() {
  return (
    <div className="flex min-h-svh flex-col bg-background md:flex-row">
      <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r bg-sidebar p-4 md:flex">
        <Link to="/" className="px-3 text-lg font-semibold">
          ResumeForge
        </Link>
        <NavLinks className="flex flex-col gap-1" />
      </aside>

      <header className="flex flex-col gap-3 border-b bg-sidebar p-4 md:hidden">
        <Link to="/" className="text-lg font-semibold">
          ResumeForge
        </Link>
        <NavLinks className="flex gap-1 overflow-x-auto" />
      </header>

      <main className="flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  )
}
