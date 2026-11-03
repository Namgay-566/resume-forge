import { Link, useMatch } from 'react-router'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

import { NAV_GROUPS, SETTINGS_ITEM, type NavItem } from './nav'

interface SidebarNavProps {
  collapsed?: boolean
  /** Called after a link is chosen (closes the mobile drawer). */
  onNavigate?: () => void
}

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-6">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="flex flex-col gap-1">
          <p
            className={cn(
              'px-3 pb-1 text-[11px] font-semibold tracking-[0.08em] text-muted-foreground uppercase transition-opacity',
              collapsed && 'sr-only',
            )}
          >
            {group.label}
          </p>
          {group.items.map((item) => (
            <SidebarLink key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
          ))}
        </div>
      ))}
      <div className="mt-auto flex flex-col gap-1">
        <SidebarLink item={SETTINGS_ITEM} collapsed={collapsed} onNavigate={onNavigate} />
      </div>
    </nav>
  )
}

function SidebarLink({ item, collapsed, onNavigate }: { item: NavItem; collapsed: boolean; onNavigate?: () => void }) {
  const { to, label, icon: Icon } = item
  // Plain strings, not NavLink's className function: the collapsed tooltip wraps the link in
  // a Radix Slot, which merges className as text and would stringify a function.
  const isActive = useMatch({ path: to, end: false }) !== null
  const link = (
    <Link
      to={to}
      onClick={onNavigate}
      aria-label={collapsed ? label : undefined}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'group/link relative flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-[color,background-color] duration-150 outline-none focus-visible:ring-3 focus-visible:ring-ring/40',
        collapsed && 'justify-center px-0',
        isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
      )}
    >
      {/* Active marker: a short brand bar on the leading edge. */}
      <span
        aria-hidden
        className={cn(
          'absolute top-1/2 -left-3 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary transition-opacity',
          isActive ? 'opacity-100' : 'opacity-0',
        )}
      />
      <Icon className={cn('size-[18px] shrink-0', isActive ? 'text-primary' : 'text-muted-foreground group-hover/link:text-foreground')} aria-hidden />
      <span className={cn('truncate', collapsed && 'sr-only')}>{label}</span>
    </Link>
  )
  if (!collapsed) return link
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  )
}
