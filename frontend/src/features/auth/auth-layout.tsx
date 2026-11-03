import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'
import { ThemeToggle } from '@/features/theme/theme-toggle'

import { PROVIDERS } from './providers'

const loginUrl = (provider: string) => `${import.meta.env.VITE_API_URL}/auth/${provider}/login`

interface AuthLayoutProps {
  title: string
  description: string
  children: ReactNode
  footer: ReactNode
}

export function AuthLayout({ title, description, children, footer }: AuthLayoutProps) {
  return (
    <main className="relative flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 px-4 py-10">
      <ThemeToggle className="absolute top-4 right-4" />
      <Link to="/" className="font-heading text-lg font-semibold">
        ResumeForge
      </Link>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <h1 className="font-heading text-h3">{title}</h1>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <ul className="flex flex-col gap-2" aria-label="Continue with">
            {PROVIDERS.map(({ id, label, Icon, iconClass }) => (
              <li key={id}>
                <Button asChild variant="outline" className="w-full">
                  <a href={loginUrl(id)}>
                    <Icon className={iconClass} aria-hidden /> Continue with {label}
                  </a>
                </Button>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            or use your email
            <span className="h-px flex-1 bg-border" />
          </div>
          {children}
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">{footer}</p>
    </main>
  )
}
