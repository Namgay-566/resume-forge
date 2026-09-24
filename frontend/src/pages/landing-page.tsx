import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

export function LandingPage() {
  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="flex items-center justify-between px-4 py-4 md:px-8">
        <span className="text-lg font-semibold">ResumeForge</span>
        <Button asChild variant="ghost">
          <Link to="/app">Open app</Link>
        </Button>
      </header>

      <main className="mx-auto flex max-w-3xl flex-1 flex-col items-center justify-center gap-6 px-4 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-balance md:text-6xl">
          Build a resume that passes ATS and gets you the job
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground text-pretty">
          Pick your target role, see exactly which skills you are missing, prove them with real
          projects, and put verified skills straight onto your resume.
        </p>
        <Button asChild size="lg">
          <Link to="/app">Get started</Link>
        </Button>
      </main>
    </div>
  )
}
