import { ChevronDown, LayoutDashboard, LogOut, Settings } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { Avatar } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/features/auth/use-auth'

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [pending, setPending] = useState(false)
  if (!user) return null

  const onLogout = async () => {
    setPending(true)
    try {
      await logout()
    } finally {
      navigate('/login', { replace: true })
    }
  }

  return (
    // Non-modal: a modal menu aria-hides the page while it stays focusable (axe: aria-hidden-focus).
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger
        className="flex items-center gap-2 rounded-full p-0.5 pr-1.5 transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/40 data-[state=open]:bg-muted sm:pr-2"
        aria-label={`Account menu for ${user.name}`}
      >
        <Avatar name={user.name} />
        <span className="hidden max-w-32 truncate text-sm font-medium lg:inline">{user.name}</span>
        <ChevronDown className="hidden size-4 text-muted-foreground sm:block" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="flex items-center gap-3 px-2 py-2 font-normal">
          <Avatar name={user.name} className="size-9" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-foreground">{user.name}</span>
            <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/dashboard">
            <LayoutDashboard /> Dashboard
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/settings">
            <Settings /> Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" disabled={pending} onSelect={() => void onLogout()}>
          <LogOut /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
