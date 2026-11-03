import { FileText, Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { domAnimation, LazyMotion, m, MotionConfig } from 'framer-motion'
import { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router'

import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ThemeToggle } from '@/features/theme/theme-toggle'
import { cn } from '@/lib/utils'
import { formatTitle } from '@/lib/use-document-title'

import { pageTitle } from './nav'
import { SidebarNav } from './sidebar-nav'
import { UserMenu } from './user-menu'

const COLLAPSED_KEY = 'rf-sidebar-collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function Brand({ collapsed = false, onClick }: { collapsed?: boolean; onClick?: () => void }) {
  return (
    <Link
      to="/dashboard"
      onClick={onClick}
      className={cn('flex h-9 items-center gap-2.5 rounded-lg font-heading text-[1.0625rem] font-semibold tracking-tight outline-none focus-visible:ring-3 focus-visible:ring-ring/40', collapsed ? 'justify-center' : 'px-1')}
      aria-label="ResumeForge, go to dashboard"
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
        <FileText className="size-4" aria-hidden />
      </span>
      <span className={cn(collapsed && 'sr-only')}>ResumeForge</span>
    </Link>
  )
}

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { pathname } = useLocation()
  const title = pageTitle(pathname)

  const toggleCollapsed = useCallback(() => {
    setCollapsed((value) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, value ? '0' : '1')
      } catch {
        // storage blocked: still toggles for this visit
      }
      return !value
    })
  }, [])

  // Ctrl/Cmd+B toggles the sidebar, as in most editors.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'b' && !event.shiftKey && !event.altKey) {
        event.preventDefault()
        toggleCollapsed()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggleCollapsed])

  // Route-level default; pages with a more specific title (a resume's name) override it.
  useLayoutEffect(() => {
    document.title = formatTitle(title)
  }, [title])

  return (
    <TooltipProvider>
      <div className="flex min-h-svh bg-background">
        {/* Desktop sidebar */}
        <aside
          className={cn(
            'sticky top-0 hidden h-svh shrink-0 flex-col gap-6 border-r bg-sidebar px-3 py-4 transition-[width] duration-200 ease-out-soft md:flex',
            collapsed ? 'w-[4.25rem]' : 'w-60',
          )}
        >
          <Brand collapsed={collapsed} />
          <SidebarNav collapsed={collapsed} />
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size={collapsed ? 'icon' : 'default'}
                onClick={toggleCollapsed}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                aria-expanded={!collapsed}
                className={cn('text-muted-foreground', collapsed ? 'self-center' : 'justify-start px-3')}
              >
                {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
                {!collapsed && <span>Collapse</span>}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {collapsed ? 'Expand' : 'Collapse'} sidebar <kbd className="ml-1 font-mono opacity-70">Ctrl B</kbd>
            </TooltipContent>
          </Tooltip>
        </aside>

        {/* Mobile drawer */}
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent side="left" className="w-72 gap-6 bg-sidebar px-3 py-4 md:hidden">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SheetDescription className="sr-only">Go to a section of ResumeForge</SheetDescription>
            <Brand onClick={() => setDrawerOpen(false)} />
            <SidebarNav onNavigate={() => setDrawerOpen(false)} />
          </SheetContent>
        </Sheet>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-md md:px-8">
            <Button variant="ghost" size="icon-sm" className="-ml-1 md:hidden" onClick={() => setDrawerOpen(true)} aria-label="Open navigation">
              <Menu />
            </Button>
            <p className="min-w-0 flex-1 truncate font-heading text-[0.9375rem] font-semibold tracking-tight">{title}</p>
            <div className="flex items-center gap-1.5">
              <ThemeToggle />
              <UserMenu />
            </div>
          </header>
          <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
            {/* Subtle page enter: keyed by path, so filters and tabs inside a page don't replay it. */}
            <LazyMotion features={domAnimation} strict>
              <MotionConfig reducedMotion="user">
                <m.div
                  key={pathname}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                >
                  <Outlet />
                </m.div>
              </MotionConfig>
            </LazyMotion>
          </main>
        </div>
      </div>
    </TooltipProvider>
  )
}
