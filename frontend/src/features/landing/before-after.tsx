import { AnimatePresence, m } from 'framer-motion'
import { ArrowDown, ArrowRight, Check, Pause, Play, Sparkles, X } from 'lucide-react'
import { Fragment } from 'react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { BULLET_EXAMPLES } from './examples'
import { Placeholder } from './features'
import { Reveal } from './motion'
import { SectionHeading } from './section-heading'
import { useRotation } from './use-rotation'

const STRONG_POINTS = ['Action verb first', 'What you did, and how', 'A result, with your real number']

/** "Cooked up to [X] covers" -> text with the placeholder highlighted. */
function WithPlaceholders({ text }: { text: string }) {
  return text.split(/(\[[^\]]+\])/).map((part, i) =>
    part.startsWith('[') ? <Placeholder key={i}>{part}</Placeholder> : <Fragment key={i}>{part}</Fragment>,
  )
}

export function BeforeAfter() {
  const rotation = useRotation(BULLET_EXAMPLES.length, 7000)
  const ex = BULLET_EXAMPLES[rotation.index]
  return (
    <section id="before-after" className="scroll-mt-20 border-y bg-muted/40">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-4 py-20 sm:px-6 md:py-24 lg:px-8">
        <SectionHeading eyebrow="Before & after" title="One bullet, rewritten the way recruiters in your field read">
          The AI works from what you wrote and uses the language of your field. Numbers it can&apos;t know are left for
          you, so nothing on your resume is made up.
        </SectionHeading>

        <div className="flex flex-wrap items-center justify-center gap-2" {...rotation.holdProps}>
          <div role="group" aria-label="Example field" className="flex flex-wrap justify-center gap-2">
            {BULLET_EXAMPLES.map((example, i) => (
              <button
                key={example.field}
                type="button"
                aria-pressed={i === rotation.index}
                onClick={() => rotation.select(i)}
                className={cn(
                  'rounded-full border px-3 py-1 text-sm transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/40',
                  i === rotation.index ? 'border-primary bg-primary text-primary-foreground' : 'bg-card text-muted-foreground hover:text-foreground',
                )}
              >
                {example.field}
              </button>
            ))}
          </div>
          {rotation.canRotate && (
            <button
              type="button"
              onClick={rotation.togglePause}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/40"
            >
              {rotation.paused ? <Play className="size-3.5" aria-hidden /> : <Pause className="size-3.5" aria-hidden />}
              {rotation.paused ? 'Play' : 'Pause'}
            </button>
          )}
        </div>

        <div className="grid items-center gap-4 lg:grid-cols-[1fr_auto_1fr] lg:gap-6" aria-live={rotation.paused ? 'polite' : 'off'} {...rotation.holdProps}>
          <Reveal className="flex h-full flex-col gap-5 rounded-2xl border bg-card/70 p-6 sm:p-7">
            <Badge variant="secondary" className="w-fit">
              Before · {ex.role}
            </Badge>
            <AnimatePresence mode="wait" initial={false}>
              <m.div key={ex.field} className="flex flex-1 flex-col gap-5" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
                <p className="font-heading text-xl leading-snug text-muted-foreground sm:text-2xl">“{ex.before}”</p>
                <ul className="mt-auto flex flex-col gap-2 text-sm">
                  {ex.weak.map((issue) => (
                    <li key={issue} className="flex items-center gap-2 text-muted-foreground">
                      <span className="flex size-5 items-center justify-center rounded-full bg-danger-muted text-danger-text">
                        <X className="size-3" aria-hidden />
                      </span>
                      {issue}
                    </li>
                  ))}
                </ul>
              </m.div>
            </AnimatePresence>
          </Reveal>

          <Reveal delay={0.15} className="flex justify-center" y={0}>
            <span className="flex size-11 items-center justify-center rounded-full border bg-card text-primary shadow-sm">
              <ArrowDown className="size-5 lg:hidden" aria-hidden />
              <ArrowRight className="hidden size-5 lg:block" aria-hidden />
              <span className="sr-only">becomes</span>
            </span>
          </Reveal>

          <Reveal delay={0.25} className="relative flex h-full flex-col gap-5 overflow-hidden rounded-2xl border border-primary/25 bg-card p-6 shadow-lg sm:p-7">
            <div aria-hidden className="pointer-events-none absolute -top-20 -right-20 size-56 rounded-full bg-brand-300/25 blur-3xl dark:bg-brand-500/20" />
            <Badge className="relative w-fit">
              <Sparkles /> After · AI-improved
            </Badge>
            <AnimatePresence mode="wait" initial={false}>
              <m.p key={ex.field} className="relative font-heading text-xl leading-snug sm:text-2xl" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
                “<WithPlaceholders text={ex.after} />”
              </m.p>
            </AnimatePresence>
            <ul className="relative mt-auto flex flex-col gap-2 text-sm">
              {STRONG_POINTS.map((point) => (
                <li key={point} className="flex items-center gap-2">
                  <span className="flex size-5 items-center justify-center rounded-full bg-success-muted text-success-text">
                    <Check className="size-3" aria-hidden />
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  )
}
