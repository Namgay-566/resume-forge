import {
  ArrowRight,
  CircleAlert,
  FileText,
  Loader2,
  Plus,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Upload,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  RADII,
  SCALE_STEPS,
  SHADOWS,
  SPACING,
  STATUSES,
  SURFACES,
  TYPE_SCALE,
} from '@/features/design-system/tokens'
import { ThemeToggle } from '@/features/theme/theme-toggle'
import { cn } from '@/lib/utils'
import { useDocumentTitle } from '@/lib/use-document-title'

const SECTIONS = [
  ['brand', 'Brand'],
  ['color', 'Color'],
  ['type', 'Typography'],
  ['space', 'Spacing, radius, shadow'],
  ['buttons', 'Buttons'],
  ['badges', 'Badges'],
  ['inputs', 'Inputs'],
  ['cards', 'Cards'],
  ['tabs', 'Tabs'],
  ['overlays', 'Dialog & toast'],
] as const

/** Dev-only reference for the design system (not routed in production builds). */
export function DesignSystemPage() {
  useDocumentTitle('Design system')
  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-8">
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <FileText className="size-4" aria-hidden />
            </span>
            <span className="font-heading font-semibold">ResumeForge</span>
            <Badge variant="secondary">Design system · dev only</Badge>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl gap-10 px-4 py-10 md:px-8">
        <nav aria-label="Sections" className="sticky top-20 hidden h-fit w-44 shrink-0 flex-col gap-0.5 lg:flex">
          {SECTIONS.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              className="rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {label}
            </a>
          ))}
        </nav>

        <main className="flex min-w-0 flex-1 flex-col gap-16">
          <BrandSection />
          <ColorSection />
          <TypeSection />
          <SpaceSection />
          <ButtonsSection />
          <BadgesSection />
          <InputsSection />
          <CardsSection />
          <TabsSection />
          <OverlaysSection />
        </main>
      </div>
    </div>
  )
}

function Section({ id, eyebrow, title, intro, children }: { id: string; eyebrow: string; title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-24 flex-col gap-6">
      <div className="flex max-w-2xl flex-col gap-2">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={`${id}-title`} className="text-h2">
          {title}
        </h2>
        {intro && <p className="text-muted-foreground">{intro}</p>}
      </div>
      {children}
    </section>
  )
}

function Row({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className={cn('flex flex-wrap items-center gap-3', className)}>{children}</div>
    </div>
  )
}

// --- Brand ------------------------------------------------------------------------------

function BrandSection() {
  return (
    <section id="brand" className="flex scroll-mt-24 flex-col gap-6">
      <div className="relative overflow-hidden rounded-3xl border bg-card p-8 shadow-md md:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full opacity-60 blur-3xl"
          style={{ background: 'radial-gradient(circle, var(--color-ember-300), transparent 70%)' }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 -left-16 size-80 rounded-full opacity-50 blur-3xl"
          style={{ background: 'radial-gradient(circle, var(--color-brand-300), transparent 70%)' }}
        />
        <div className="relative flex max-w-2xl flex-col gap-4">
          <p className="eyebrow">Professional · confident · modern · encouraging</p>
          <h1 className="text-display">I can get this job.</h1>
          <p className="text-base text-muted-foreground">
            Clean and precise like a well-made tool, but warmer. We&apos;re on the job seeker&apos;s side:
            calm surfaces, a confident indigo for action, and a warm ember for progress worth celebrating.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Button size="lg">
              Build my resume <ArrowRight />
            </Button>
            <Button size="lg" variant="outline">
              <Upload /> Import a resume
            </Button>
          </div>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Principle title="Why deep indigo" icon={<ShieldCheck className="size-4" />}>
          Indigo reads as trust and competence, without the corporate blue of LinkedIn or job boards. It also
          sits far from green, so the brand color never looks like &ldquo;verified&rdquo;.
        </Principle>
        <Principle title="Why ember" icon={<Sparkles className="size-4" />}>
          A warm tangerine for encouragement: progress, &ldquo;almost there&rdquo;, the next best action. It&apos;s
          decorative only, never a status, so it can&apos;t be mistaken for a warning.
        </Principle>
        <Principle title="Why warm neutrals" icon={<FileText className="size-4" />}>
          Light mode uses paper-toned grays instead of cold ones; dark mode uses indigo ink. Same structure as
          Linear or Vercel, with more warmth.
        </Principle>
      </div>
    </section>
  )
}

function Principle({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <span className="flex size-7 items-center justify-center rounded-md bg-secondary text-secondary-foreground">{icon}</span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-muted-foreground">{children}</CardContent>
    </Card>
  )
}

// --- Color ------------------------------------------------------------------------------

function ColorSection() {
  return (
    <Section
      id="color"
      eyebrow="Tokens"
      title="Color"
      intro="Components use semantic tokens (bg-primary, text-muted-foreground, bg-success-muted…), never raw scale steps. Every text-on-surface pair passes WCAG AA in both modes."
    >
      <Scale name="brand" label="Brand · indigo" />
      <Scale name="ember" label="Accent · ember" />

      <div className="flex flex-col gap-3">
        <p className="text-sm font-medium">Surfaces and text, light and dark</p>
        <div className="grid gap-4 md:grid-cols-2">
          {(['light', 'dark'] as const).map((mode) => (
            <div key={mode} className={cn(mode, 'flex flex-col gap-2 rounded-2xl border bg-background p-4 text-foreground')}>
              <p className="eyebrow">{mode}</p>
              {SURFACES.map((t) => (
                <div
                  key={t.name}
                  className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5"
                  style={{ background: `var(${t.variable})`, color: t.on ? `var(${t.on})` : undefined }}
                >
                  <span className="font-mono text-xs">{t.name}</span>
                  <span className="text-xs">{t.use}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <p className="text-sm font-medium">Status: always with an icon or a word, never color alone</p>
        <div className="grid gap-4 md:grid-cols-2">
          {(['light', 'dark'] as const).map((mode) => (
            <div key={mode} className={cn(mode, 'flex flex-col gap-3 rounded-2xl border bg-background p-4 text-foreground')}>
              <p className="eyebrow">{mode}</p>
              {STATUSES.map((s) => (
                <div key={s.key} className="grid grid-cols-[auto_1fr] items-center gap-3">
                  <span
                    className="flex h-9 w-20 items-center justify-center rounded-md text-xs font-semibold"
                    style={{ background: `var(--${s.key})`, color: `var(--${s.key}-foreground)` }}
                  >
                    {s.label}
                  </span>
                  <span
                    className="flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-medium"
                    style={{
                      background: `var(--${s.key}-muted)`,
                      color: `var(--${s.key}-text)`,
                      borderColor: `color-mix(in oklch, var(--${s.key}) 30%, transparent)`,
                    }}
                  >
                    <StatusIcon status={s.key} />
                    {s.meaning}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Each status has four tokens: <code className="font-mono">--success</code> (solid),{' '}
          <code className="font-mono">-foreground</code> (text on solid), <code className="font-mono">-muted</code> (soft
          background) and <code className="font-mono">-text</code> (readable text on the page or the soft background).
        </p>
      </div>
    </Section>
  )
}

function Scale({ name, label }: { name: 'brand' | 'ember'; label: string }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium">{label}</p>
      <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-11">
        {SCALE_STEPS.map((step) => (
          <div key={step} className="flex flex-col gap-1">
            <div className="h-12 rounded-md border border-black/5" style={{ background: `var(--color-${name}-${step})` }} />
            <span className="font-mono text-[11px] text-muted-foreground">{step}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function StatusIcon({ status }: { status: 'success' | 'warning' | 'danger' }) {
  if (status === 'success') return <ShieldCheck className="size-4 shrink-0" aria-hidden />
  if (status === 'warning') return <TriangleAlert className="size-4 shrink-0" aria-hidden />
  return <CircleAlert className="size-4 shrink-0" aria-hidden />
}

// --- Typography -------------------------------------------------------------------------

function TypeSection() {
  return (
    <Section id="type" eyebrow="Tokens" title="Typography" intro="Self-hosted from Google Fonts (via @fontsource) so the strict production CSP holds.">
      <div className="grid gap-4 md:grid-cols-3">
        <FontCard family="font-heading" name="Bricolage Grotesque" role="Headings" note="Warm, confident grotesque with optical sizing: tight and characterful large, calm small.">
          Aa Gg 123
        </FontCard>
        <FontCard family="font-sans" name="Instrument Sans" role="Body & UI" note="Clean and highly legible at 14px, with more warmth than Inter or Geist.">
          Aa Gg 123
        </FontCard>
        <FontCard family="font-mono" name="JetBrains Mono" role="Code & IDs" note="Credential IDs, tokens, code samples. Scores use tabular numerals.">
          ID-3F9A
        </FontCard>
      </div>
      <Card>
        <CardContent className="flex flex-col divide-y">
          {TYPE_SCALE.map((t) => (
            <div key={t.token} className="grid gap-2 py-4 first:pt-0 last:pb-0 md:grid-cols-[9rem_1fr] md:items-baseline">
              <div className="flex flex-col">
                <code className="font-mono text-xs">{t.token}</code>
                <span className="text-xs text-muted-foreground">{t.size}</span>
              </div>
              <p className={cn(t.token, t.token.startsWith('text-h') || t.token === 'text-display' ? 'font-heading' : '')}>{t.sample}</p>
            </div>
          ))}
          <div className="grid gap-2 py-4 last:pb-0 md:grid-cols-[9rem_1fr] md:items-baseline">
            <code className="font-mono text-xs">eyebrow</code>
            <p className="eyebrow">Next best action</p>
          </div>
        </CardContent>
      </Card>
    </Section>
  )
}

function FontCard({ family, name, role, note, children }: { family: string; name: string; role: string; note: string; children: ReactNode }) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-3">
        <p className={cn(family, 'text-5xl leading-none font-semibold tracking-tight')}>{children}</p>
        <div>
          <p className="font-medium">{name}</p>
          <p className="text-xs text-muted-foreground">{role}</p>
        </div>
        <p className="text-xs text-muted-foreground">{note}</p>
      </CardContent>
    </Card>
  )
}

// --- Spacing, radius, shadow ---------------------------------------------------------------

function SpaceSection() {
  return (
    <Section id="space" eyebrow="Tokens" title="Spacing, radius, shadow" intro="A 4px grid. Inside components use 1–4 (4–16px); between blocks 4–8; between page sections 12–16.">
      <Card>
        <CardContent className="flex flex-col gap-2">
          {SPACING.map((n) => (
            <div key={n} className="flex items-center gap-3">
              <code className="w-10 font-mono text-xs text-muted-foreground">{n}</code>
              <div className="h-3 rounded-sm bg-primary/70" style={{ width: `calc(var(--spacing) * ${n})` }} />
              <span className="text-xs text-muted-foreground">{n * 4}px</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {RADII.map((r) => (
          <div key={r.token} className="flex flex-col gap-2">
            <div className={cn(r.token, 'h-16 border bg-secondary')} />
            <code className="font-mono text-xs">{r.token}</code>
            <span className="text-xs text-muted-foreground">
              {r.px === 999 ? 'full' : `${r.px}px`} · {r.use}
            </span>
          </div>
        ))}
      </div>
      <div className="grid gap-4 rounded-2xl bg-muted p-6 sm:grid-cols-3 lg:grid-cols-5">
        {SHADOWS.map((s) => (
          <div key={s.token} className="flex flex-col gap-2">
            <div className={cn(s.token, 'h-20 rounded-xl bg-card')} />
            <code className="font-mono text-xs">{s.token}</code>
            <span className="text-xs text-muted-foreground">{s.use}</span>
          </div>
        ))}
      </div>
    </Section>
  )
}

// --- Components -------------------------------------------------------------------------

const VARIANTS = ['default', 'highlight', 'secondary', 'outline', 'ghost', 'destructive', 'link'] as const

/** Example people for the component demos: every field, not only tech. */
const PEOPLE = [
  { id: 'nurse', name: 'Priya Shah', role: 'Registered Nurse', skill: 'Basic Life Support (BLS)', status: 'danger', label: 'Missing · critical' },
  { id: 'accountant', name: 'Daniel Okoye', role: 'Financial Analyst', skill: 'Financial modelling', status: 'warning', label: 'Unverified' },
  { id: 'designer', name: 'Mei Tan', role: 'Graphic Designer', skill: 'Brand identity', status: 'success', label: 'Verified' },
  { id: 'electrician', name: 'Tom Walsh', role: 'Electrician', skill: '18th Edition Wiring Regulations', status: 'success', label: 'Verified' },
] as const

function ButtonsSection() {
  return (
    <Section id="buttons" eyebrow="Component" title="Buttons" intro="One primary (indigo) action per view. Highlight (ember) is for encouraging moments like “Add to resume”.">
      <Row label="Variants">
        {VARIANTS.map((v) => (
          <Button key={v} variant={v}>
            {v === 'default' ? 'Primary' : v[0].toUpperCase() + v.slice(1)}
          </Button>
        ))}
      </Row>
      <Row label="Sizes">
        <Button size="xs">Extra small</Button>
        <Button size="sm">Small</Button>
        <Button>Default</Button>
        <Button size="lg">Large</Button>
        <Button size="icon-sm" variant="outline" aria-label="Add">
          <Plus />
        </Button>
        <Button size="icon" variant="outline" aria-label="Add">
          <Plus />
        </Button>
      </Row>
      <Row label="With icons and states">
        <Button>
          <Sparkles /> Improve with AI
        </Button>
        <Button variant="highlight">
          <ShieldCheck /> Add verified skill
        </Button>
        <Button variant="outline">
          Continue <ArrowRight />
        </Button>
        <Button disabled>
          <Loader2 className="animate-spin" /> Saving…
        </Button>
        <Button variant="outline" disabled>
          Disabled
        </Button>
      </Row>
    </Section>
  )
}

function BadgesSection() {
  return (
    <Section id="badges" eyebrow="Component" title="Badges">
      <Row label="Variants">
        <Badge>Registered Nurse</Badge>
        <Badge variant="secondary">Financial Analyst</Badge>
        <Badge variant="solid">Solid</Badge>
        <Badge variant="outline">Outline</Badge>
        <Badge variant="highlight">
          <Sparkles /> Almost there
        </Badge>
      </Row>
      <Row label="Skill status">
        <Badge variant="success">
          <ShieldCheck /> Verified
        </Badge>
        <Badge variant="warning">
          <TriangleAlert /> Unverified
        </Badge>
        <Badge variant="danger">
          <CircleAlert /> Missing · critical
        </Badge>
      </Row>
      <Card size="sm" className="max-w-md">
        <CardContent className="flex flex-col divide-y text-sm">
          {PEOPLE.map(({ id, role, skill, status, label }) => (
            <div key={id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
              <span className="min-w-0">
                <span className="block font-medium">{skill}</span>
                <span className="block text-xs text-muted-foreground">{role}</span>
              </span>
              <Badge variant={status}>
                <StatusIcon status={status} /> {label}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </Section>
  )
}

function InputsSection() {
  return (
    <Section id="inputs" eyebrow="Component" title="Inputs">
      <div className="grid max-w-2xl gap-5 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="ds-name">Full name</Label>
          <Input id="ds-name" placeholder="Priya Shah" />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ds-email">Email</Label>
          <Input id="ds-email" defaultValue="priya@example" aria-invalid aria-describedby="ds-email-error" />
          <p id="ds-email-error" className="text-sm text-danger-text">
            Enter a valid email address
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ds-role">Target role</Label>
          <Select defaultValue="nurse">
            <SelectTrigger id="ds-role" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PEOPLE.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.role}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ds-disabled">Disabled</Label>
          <Input id="ds-disabled" disabled defaultValue="Read only" />
        </div>
        <div className="flex flex-col gap-2 md:col-span-2">
          <Label htmlFor="ds-summary">Professional summary</Label>
          <Textarea id="ds-summary" placeholder="Two or three sentences on who you are and what you're aiming for." />
          <p className="text-xs text-muted-foreground">Helper text sits below, in muted-foreground.</p>
        </div>
      </div>
    </Section>
  )
}

function CardsSection() {
  return (
    <Section id="cards" eyebrow="Component" title="Cards">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Default</CardTitle>
            <CardDescription>Border and a soft shadow. Most content.</CardDescription>
          </CardHeader>
          <CardContent className="text-muted-foreground">Resume cards, form sections.</CardContent>
        </Card>
        <Card variant="elevated">
          <CardHeader>
            <CardTitle>Elevated</CardTitle>
            <CardDescription>For the one thing that matters most.</CardDescription>
          </CardHeader>
          <CardContent className="text-muted-foreground">Hero stats, next best action.</CardContent>
        </Card>
        <Card variant="muted">
          <CardHeader>
            <CardTitle>Muted</CardTitle>
            <CardDescription>Recessed, secondary content.</CardDescription>
          </CardHeader>
          <CardContent className="text-muted-foreground">Tips, empty states.</CardContent>
        </Card>
        <Card variant="highlight">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-4 text-highlight-text" aria-hidden /> You&apos;re close
            </CardTitle>
            <CardDescription>Two skills away from job-ready.</CardDescription>
          </CardHeader>
          <CardContent className="text-muted-foreground">Encouraging moments only.</CardContent>
        </Card>
      </div>
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>With a footer</CardTitle>
          <CardDescription>Actions go in the footer, primary on the right.</CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground">Readiness for Financial Analyst went from 40% to 56% this week.</CardContent>
        <CardFooter className="justify-end">
          <Button variant="ghost" size="sm">
            Later
          </Button>
          <Button size="sm">Open roadmap</Button>
        </CardFooter>
      </Card>
    </Section>
  )
}

function TabsSection() {
  return (
    <Section id="tabs" eyebrow="Component" title="Tabs">
      <Row label="Default (segmented)" className="block">
        <Tabs defaultValue="edit" className="max-w-md">
          <TabsList>
            <TabsTrigger value="edit">Edit</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="ats">ATS check</TabsTrigger>
          </TabsList>
          <TabsContent value="edit" className="pt-3 text-muted-foreground">Edit your resume content.</TabsContent>
          <TabsContent value="preview" className="pt-3 text-muted-foreground">See it as a recruiter would.</TabsContent>
          <TabsContent value="ats" className="pt-3 text-muted-foreground">Check how ATS software reads it.</TabsContent>
        </Tabs>
      </Row>
      <Row label="Line (page-level navigation)" className="block">
        <Tabs defaultValue="licence" className="max-w-md">
          <TabsList variant="line">
            <TabsTrigger value="licence">Licence</TabsTrigger>
            <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
            <TabsTrigger value="sample">Work sample</TabsTrigger>
          </TabsList>
          <TabsContent value="licence" className="pt-3 text-muted-foreground">Upload a nursing registration, trade licence or certificate.</TabsContent>
          <TabsContent value="portfolio" className="pt-3 text-muted-foreground">Link a Behance page or your own portfolio site.</TabsContent>
          <TabsContent value="sample" className="pt-3 text-muted-foreground">Upload a care plan, financial model or lesson plan.</TabsContent>
        </Tabs>
      </Row>
    </Section>
  )
}

function OverlaysSection() {
  return (
    <Section id="overlays" eyebrow="Component" title="Dialog & toast">
      <Row label="Dialog">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Open dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Brand identity to your resume?</DialogTitle>
              <DialogDescription>Your Behance portfolio proved it. We&apos;ll add it to Skills with the proof link.</DialogDescription>
            </DialogHeader>
            <Badge variant="success" className="w-fit">
              <ShieldCheck /> Verified by behance.net/meitan
            </Badge>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="ghost">Not now</Button>
              </DialogClose>
              <DialogClose asChild>
                <Button variant="highlight" onClick={() => toast.success('Brand identity added to Skills')}>
                  Add to resume
                </Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Row>
      <Row label="Toast">
        <Button variant="outline" onClick={() => toast.success('Basic Life Support is now verified', { description: 'Readiness for Registered Nurse went from 40% to 56%.' })}>
          Success
        </Button>
        <Button variant="outline" onClick={() => toast.warning('3 skills are still unverified', { description: 'Upload proof to get them verified.' })}>
          Warning
        </Button>
        <Button variant="outline" onClick={() => toast.error("Couldn't save your resume", { description: 'Check your connection and try again.' })}>
          Error
        </Button>
        <Button variant="outline" onClick={() => toast('Resume duplicated', { action: { label: 'Open', onClick: () => undefined } })}>
          With action
        </Button>
        <Button variant="outline" onClick={() => toast.promise(new Promise((r) => setTimeout(r, 1500)), { loading: 'Exporting PDF…', success: 'PDF ready', error: 'Export failed' })}>
          Loading → done
        </Button>
      </Row>
    </Section>
  )
}
