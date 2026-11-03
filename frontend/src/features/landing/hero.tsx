import { AnimatePresence, m } from 'framer-motion'
import { ArrowRight, Check, CircleAlert, Gauge, Pause, Play, ShieldCheck, Sparkles, TrendingUp } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { HERO_EXAMPLES } from './examples'
import { ScoreRing } from './motion'
import { useRotation } from './use-rotation'

const EASE = [0.22, 1, 0.36, 1] as const
const PROOF_POINTS = [
  'Single-column, ATS-safe PDF and DOCX',
  'Skills verified from licences, certificates and real work',
  'AI that never invents your numbers',
]
const FIELDS = 'Nurses, teachers, accountants, marketers, chefs, electricians, developers and more'


export function Hero({ buildHref, scoreHref }: { buildHref: string; scoreHref: string }) {
  return (
    <section className="relative isolate overflow-hidden">
      <Backdrop />
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-12 pb-20 sm:px-6 md:pt-20 lg:grid-cols-[1.05fr_1fr] lg:gap-10 lg:px-8 lg:pt-24 lg:pb-28">
        <div className="flex flex-col items-start gap-6">
          <m.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE }}>
            <Badge variant="highlight" className="h-7 px-3 text-[0.8125rem]">
              <Sparkles /> ATS score · skill gaps · verified proof
            </Badge>
          </m.div>
          <m.h1
            className="text-[2.5rem] leading-[1.05] font-[650] tracking-[-0.035em] sm:text-5xl lg:text-[3.5rem]"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.05 }}
          >
            Pass the ATS. Then learn <span className="text-primary">exactly</span> the skills that get you hired.
          </m.h1>
          <m.p
            className="max-w-xl text-lg text-muted-foreground"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.12 }}
          >
            ResumeForge scores your resume the way applicant tracking systems read it, shows which skills your
            target role needs that you&apos;re missing, and helps you prove them with real work, whatever your field.
          </m.p>
          <m.p
            className="-mt-2 text-sm font-medium text-foreground/80"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.16 }}
          >
            {FIELDS}. Students and career changers too.
          </m.p>
          <m.div
            className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.18 }}
          >
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link to={buildHref}>
                Build my resume <ArrowRight />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
              <Link to={scoreHref}>
                <Gauge /> Check my resume score
              </Link>
            </Button>
          </m.div>
          <m.ul
            className="flex flex-col gap-2 pt-1 text-sm text-muted-foreground"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            {PROOF_POINTS.map((point) => (
              <li key={point} className="flex items-center gap-2">
                <span className="flex size-5 items-center justify-center rounded-full bg-success-muted text-success-text">
                  <Check className="size-3" aria-hidden />
                </span>
                {point}
              </li>
            ))}
          </m.ul>
        </div>
        <ResumeVisual />
      </div>
    </section>
  )
}

function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
      {/* Faint grid, fading out toward the edges. */}
      <div
        className="absolute inset-0 opacity-[0.55] [mask-image:radial-gradient(ellipse_70%_60%_at_60%_35%,black,transparent)] dark:opacity-40"
        style={{
          backgroundImage:
            'linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
        }}
      />
      <div className="absolute -top-40 right-[-10%] size-[36rem] rounded-full bg-brand-400/25 blur-3xl dark:bg-brand-500/20" />
      <div className="absolute top-56 right-[20%] size-72 rounded-full bg-ember-300/30 blur-3xl dark:bg-ember-500/15" />
    </div>
  )
}

/** A stylised resume with its live ATS score and skill status, cycling through job seekers
 * from different fields. Decorative: the whole card is one image for assistive tech,
 * described by its label, with a control to pause the rotation. */
function ResumeVisual() {
  const rotation = useRotation(HERO_EXAMPLES.length, 5000)
  const ex = HERO_EXAMPLES[rotation.index]
  return (
    <div className="relative mx-auto flex w-full max-w-[26rem] flex-col px-1 sm:px-8 lg:max-w-[28rem]" {...rotation.holdProps}>
      <AnimatePresence mode="wait" initial={false}>
        <m.div
          key={ex.name}
          role="img"
          aria-label={`Example resume for a ${ex.role} with an ATS score of ${ex.score}, ${ex.verified} verified, and ${ex.missing} missing`}
          className="flex flex-col"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35 }}
        >
          <m.div
            className="relative z-10 -mb-6 flex items-center gap-3 self-end rounded-2xl border bg-popover p-3 pr-4 shadow-lg sm:-mr-8"
            initial={{ opacity: 0, y: -12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.2 }}
          >
            <ScoreRing value={ex.score} size={92} />
            <div className="flex flex-col gap-1">
              <p className="text-xs font-medium">ATS check</p>
              <p className="flex items-center gap-1 text-xs font-medium text-success-text">
                <TrendingUp className="size-3.5" aria-hidden /> +{ex.gain} since last check
              </p>
            </div>
          </m.div>

          <div className="relative -rotate-[1.5deg] rounded-2xl border bg-card px-5 py-8 shadow-xl sm:px-6">
            <div className="flex items-center gap-3 border-b pb-4">
              <div className="flex size-11 items-center justify-center rounded-full bg-secondary font-heading font-semibold text-secondary-foreground">
                {ex.initials}
              </div>
              <div className="min-w-0">
                <p className="font-heading font-semibold">{ex.name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {ex.role} · {ex.city}
                </p>
              </div>
              <Badge variant="secondary" className="ml-auto shrink-0">
                {ex.field}
              </Badge>
            </div>
            <div className="flex flex-col gap-3 py-4">
              <p className="eyebrow text-[10px]">Experience</p>
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-medium">{ex.job}</p>
                <p className="shrink-0 text-[11px] text-muted-foreground">{ex.dates}</p>
              </div>
              <Line width="92%" />
              <Line width="78%" />
              <Line width="85%" />
            </div>
            <div className="flex flex-col gap-3 border-t pt-4">
              <p className="eyebrow text-[10px]">Skills</p>
              <div className="flex flex-wrap gap-1.5">
                <Chip delay={0.35}>
                  <Badge variant="success">
                    <ShieldCheck /> {ex.verified} · Verified
                  </Badge>
                </Chip>
                {ex.skills.map((skill, i) => (
                  <Chip key={skill} delay={0.45 + i * 0.1}>
                    <Badge variant="outline">{skill}</Badge>
                  </Chip>
                ))}
                <Chip delay={0.65}>
                  <Badge variant="danger" className="border-dashed">
                    <CircleAlert /> Missing: {ex.missing}
                  </Badge>
                </Chip>
              </div>
            </div>
          </div>

          <m.div
            className="relative z-10 -mt-6 flex max-w-[15rem] items-start gap-2.5 self-start rounded-xl border bg-popover p-3 shadow-lg sm:-ml-8"
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.6, ease: EASE, delay: 0.4 }}
          >
            <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-highlight-muted text-highlight-text">
              <Sparkles className="size-4" aria-hidden />
            </span>
            <div>
              <p className="eyebrow text-[10px]">Next best action</p>
              <p className="text-sm leading-snug font-medium">{ex.nextAction}</p>
            </div>
          </m.div>
        </m.div>
      </AnimatePresence>
      {rotation.canRotate && (
        <button
          type="button"
          onClick={rotation.togglePause}
          className="mt-4 inline-flex items-center gap-1.5 self-center rounded-full px-3 py-1 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/40"
        >
          {rotation.paused ? <Play className="size-3.5" aria-hidden /> : <Pause className="size-3.5" aria-hidden />}
          {rotation.paused ? 'Play examples' : 'Pause examples'}
        </button>
      )}
    </div>
  )
}

function Line({ width }: { width: string }) {
  return <div className="h-2 rounded-full bg-muted" style={{ width }} />
}

function Chip({ children, delay }: { children: React.ReactNode; delay: number }) {
  return (
    <m.span initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.35, ease: EASE, delay }}>
      {children}
    </m.span>
  )
}
