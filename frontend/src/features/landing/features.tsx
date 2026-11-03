import { m } from 'framer-motion'
import {
  BadgeCheck,
  Check,
  CircleAlert,
  FileBadge,
  Gauge,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { Reveal } from './motion'
import { SectionHeading } from './section-heading'

const EASE = [0.22, 1, 0.36, 1] as const

export function Features() {
  return (
    <section id="features" className="scroll-mt-20">
      <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-20 sm:px-6 md:py-28 lg:px-8">
        <SectionHeading eyebrow="Features" title="Everything between “apply” and “you're hired”">
          Honest scores, a clear plan, and proof that holds up, all built around your resume.
        </SectionHeading>
        <div className="grid gap-5 md:grid-cols-2">
          <FeatureCard
            icon={Gauge}
            title="ATS scoring you can act on"
            body="Scored the way applicant tracking systems read resumes: sections, dates, action verbs, results and keywords. Every fix shows the points it's worth."
            delay={0}
          >
            <AtsPreview />
          </FeatureCard>
          <FeatureCard
            icon={ScanSearch}
            title="Skill gap analysis for your target role"
            body="Choose any role, from Registered Nurse or Electrician to Accountant or Developer, and see which required skills and licences you have, which you can't back up yet, and which are missing."
            delay={0.08}
          >
            <GapPreview />
          </FeatureCard>
          <FeatureCard
            icon={ShieldCheck}
            title="Proof that fits your field"
            body="Upload a licence, certificate, work sample, portfolio, publication or reference. Each is reviewed by an AI that knows your field, and checked against the issuer or public register where it can be."
            delay={0}
          >
            <ProofPreview />
          </FeatureCard>
          <FeatureCard
            icon={Sparkles}
            title="AI bullet improver"
            body="Turn vague bullets into action, what, how and result. It never invents numbers: anything you didn't write becomes a placeholder for you to fill in."
            delay={0.08}
          >
            <BulletPreview />
          </FeatureCard>
        </div>
      </div>
    </section>
  )
}

function FeatureCard({ icon: Icon, title, body, delay, children }: { icon: LucideIcon; title: string; body: string; delay: number; children: ReactNode }) {
  return (
    <Reveal delay={delay} className="group flex min-w-0 flex-col gap-6 rounded-2xl border bg-card p-6 shadow-xs transition-shadow duration-300 hover:shadow-md sm:p-7">
      <div className="flex flex-col gap-3">
        <span className="flex size-10 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
          <Icon className="size-5" aria-hidden />
        </span>
        <h3 className="text-h4">{title}</h3>
        <p className="text-sm text-muted-foreground">{body}</p>
      </div>
      {/* Previews illustrate the feature; the text above says the same thing. */}
      <div aria-hidden className="mt-auto rounded-xl border bg-background/60 p-4 sm:p-5">
        {children}
      </div>
    </Reveal>
  )
}

function Meter({ label, value, delay }: { label: string; value: number; delay: number }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground tabular-nums">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <m.div
          className="h-full rounded-full bg-primary"
          initial={{ width: 0 }}
          whileInView={{ width: `${value}%` }}
          viewport={{ once: true, amount: 0.6 }}
          transition={{ duration: 0.9, ease: EASE, delay }}
        />
      </div>
    </div>
  )
}

function AtsPreview() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium text-muted-foreground">ATS score</p>
          <p className="font-heading text-3xl leading-none font-semibold tabular-nums">
            78<span className="text-sm font-normal text-muted-foreground"> / 100</span>
          </p>
        </div>
        <Badge variant="highlight">3 fixes · +12 points</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Meter label="Formatting" value={95} delay={0} />
        <Meter label="Keywords" value={72} delay={0.08} />
        <Meter label="Impact" value={64} delay={0.16} />
        <Meter label="Completeness" value={88} delay={0.24} />
      </div>
    </div>
  )
}

const GAP_ROWS = [
  { skill: 'Nursing licence', variant: 'success', icon: ShieldCheck, label: 'Verified' },
  { skill: 'Patient assessment', variant: 'warning', icon: TriangleAlert, label: 'Unverified' },
  { skill: 'Basic Life Support', variant: 'danger', icon: CircleAlert, label: 'Missing · critical' },
] as const

function GapPreview() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between text-xs">
          <span className="font-medium">Readiness · Registered Nurse</span>
          <span className="font-semibold text-foreground tabular-nums">64%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <m.div
            className="h-full rounded-full bg-gradient-to-r from-primary to-highlight"
            initial={{ width: 0 }}
            whileInView={{ width: '64%' }}
            viewport={{ once: true, amount: 0.6 }}
            transition={{ duration: 1, ease: EASE }}
          />
        </div>
      </div>
      <ul className="flex flex-col divide-y rounded-lg border bg-card">
        {GAP_ROWS.map(({ skill, variant, icon: Icon, label }) => (
          <li key={skill} className="flex items-center justify-between gap-2 px-3 py-2.5 text-sm">
            <span className="font-medium">{skill}</span>
            <Badge variant={variant}>
              <Icon /> {label}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ProofPreview() {
  const checks = ['Name matches yours', 'Current until 2029', 'Confirmed on the public register']
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border bg-card p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
            <BadgeCheck className="size-4 shrink-0 text-muted-foreground" />
            <span className="truncate">Registered Nurse licence</span>
          </span>
          <Badge variant="success">
            <ShieldCheck /> Verified
          </Badge>
        </div>
        <ul className="mt-3 flex flex-col gap-1.5">
          {checks.map((check, i) => (
            <m.li
              key={check}
              className="flex items-center gap-2 text-xs text-muted-foreground"
              initial={{ opacity: 0, x: -6 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.8 }}
              transition={{ duration: 0.4, ease: EASE, delay: 0.1 + i * 0.12 }}
            >
              <Check className="size-3.5 text-success-text" /> {check}
            </m.li>
          ))}
        </ul>
      </div>
      <div className="flex items-center justify-between gap-2 rounded-lg border bg-card p-3">
        <span className="flex min-w-0 items-center gap-2 text-sm">
          <FileBadge className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">
            <span className="font-medium">Food Hygiene Level 2</span>
            <span className="text-muted-foreground"> · confirmed on issuer&apos;s site</span>
          </span>
        </span>
        <Badge variant="success" className="shrink-0">
          <ShieldCheck /> Verified
        </Badge>
      </div>
    </div>
  )
}

function BulletPreview() {
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border bg-card px-3 py-2.5 text-sm text-muted-foreground line-through decoration-muted-foreground/40">
        Helped with sales to new customers.
      </div>
      <div className="flex items-center gap-2 text-xs font-medium text-primary">
        <Sparkles className="size-3.5" /> Improved
      </div>
      <m.div
        className="rounded-lg border border-primary/30 bg-card px-3 py-2.5 text-sm leading-relaxed shadow-xs"
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.8 }}
        transition={{ duration: 0.5, ease: EASE, delay: 0.15 }}
      >
        <Added>Prospected and closed</Added> <Placeholder>[X]</Placeholder> <Added>new accounts</Added>, reaching{' '}
        <Placeholder>[X%]</Placeholder> <Added>of quota</Added>.
      </m.div>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="size-2 rounded-full bg-highlight" /> Placeholders mark numbers only you know.
      </p>
    </div>
  )
}

function Added({ children }: { children: ReactNode }) {
  return <span className="rounded bg-success-muted px-0.5 text-success-text">{children}</span>
}

export function Placeholder({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn('rounded border border-dashed border-highlight/60 bg-highlight-muted px-1 font-medium text-highlight-text', className)}>
      {children}
    </span>
  )
}
