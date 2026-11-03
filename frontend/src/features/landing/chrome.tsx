import { ArrowRight, FileText, Gauge } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/features/theme/theme-toggle'
import { cn } from '@/lib/utils'

import { Reveal } from './motion'

const NAV = [
  ['#how-it-works', 'How it works'],
  ['#features', 'Features'],
  ['#faq', 'FAQ'],
] as const

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn('flex items-center gap-2 rounded-md font-heading text-lg font-semibold tracking-tight', className)}>
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
        <FileText className="size-4" aria-hidden />
      </span>
      ResumeForge
    </Link>
  )
}

export function LandingHeader({ signedIn, startHref }: { signedIn: boolean; startHref: string }) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={cn(
        'sticky top-0 z-40 border-b border-transparent transition-[background-color,border-color,box-shadow] duration-200',
        scrolled && 'border-border bg-background/80 shadow-xs backdrop-blur-lg',
      )}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Logo />
        <nav aria-label="Page sections" className="hidden items-center gap-1 md:flex">
          {NAV.map(([href, label]) => (
            <a key={href} href={href} className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">
              {label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-1 sm:gap-2">
          <ThemeToggle />
          {signedIn ? (
            <Button asChild size="sm">
              <Link to="/dashboard">Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link to="/login">Log in</Link>
              </Button>
              <Button asChild size="sm" className="hidden sm:inline-flex">
                <Link to={startHref}>Get started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

export function FinalCta({ buildHref, scoreHref }: { buildHref: string; scoreHref: string }) {
  return (
    <section className="px-4 pb-20 sm:px-6 md:pb-28 lg:px-8">
      <Reveal className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-3xl bg-brand-800 px-6 py-14 text-center text-white shadow-xl sm:px-12 md:py-20 dark:bg-brand-900">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute -top-32 left-1/2 size-[32rem] -translate-x-1/2 rounded-full bg-brand-500/50 blur-3xl" />
          <div className="absolute -right-20 -bottom-40 size-96 rounded-full bg-ember-500/35 blur-3xl" />
          <div
            className="absolute inset-0 opacity-[0.12] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]"
            style={{
              backgroundImage:
                'linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)',
              backgroundSize: '40px 40px',
            }}
          />
        </div>
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-5">
          <h2 className="text-[2rem] leading-[1.12] font-[650] tracking-[-0.03em] text-balance md:text-5xl">
            Your next job is a few verified skills away.
          </h2>
          <p className="max-w-lg text-base text-white/75 md:text-lg">
            Build the resume, see the gaps, prove the skills. Start with the resume you already have.
          </p>
          <div className="flex w-full flex-col justify-center gap-3 pt-2 sm:w-auto sm:flex-row">
            <Button asChild size="lg" variant="highlight" className="w-full sm:w-auto">
              <Link to={buildHref}>
                Build my resume <ArrowRight />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="w-full border-white/25 bg-white/10 text-white shadow-none hover:border-white/40 hover:bg-white/15 sm:w-auto"
            >
              <Link to={scoreHref}>
                <Gauge /> Check my resume score
              </Link>
            </Button>
          </div>
        </div>
      </Reveal>
    </section>
  )
}

export function LandingFooter({ signedIn }: { signedIn: boolean }) {
  const year = new Date().getFullYear()
  const columns: [string, [string, string][]][] = [
    ['Product', [['#how-it-works', 'How it works'], ['#features', 'Features'], ['#before-after', 'Before & after'], ['#faq', 'FAQ']]],
    ['Account', signedIn ? [['/dashboard', 'Dashboard'], ['/resumes', 'My resumes']] : [['/register', 'Create an account'], ['/login', 'Log in']]],
  ]
  return (
    <footer className="border-t bg-muted/30">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.5fr_1fr_1fr] lg:px-8">
        <div className="flex flex-col gap-3">
          <Logo />
          <p className="max-w-xs text-sm text-muted-foreground">
            ATS-friendly resumes, a clear skill-gap plan, and verified proof for the job you want.
          </p>
        </div>
        {columns.map(([title, links]) => (
          <div key={title} className="flex flex-col gap-3">
            <p className="text-sm font-semibold">{title}</p>
            <ul className="flex flex-col gap-2">
              {links.map(([href, label]) => (
                <li key={href}>
                  {href.startsWith('#') ? (
                    <a href={href} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                      {label}
                    </a>
                  ) : (
                    <Link to={href} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                      {label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t">
        <p className="mx-auto max-w-6xl px-4 py-6 text-xs text-muted-foreground sm:px-6 lg:px-8">© {year} ResumeForge</p>
      </div>
    </footer>
  )
}
