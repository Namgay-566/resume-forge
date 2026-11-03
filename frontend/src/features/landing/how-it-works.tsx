import { m } from 'framer-motion'
import { Briefcase, FilePen, ScanSearch, ShieldCheck, type LucideIcon } from 'lucide-react'

import { Reveal } from './motion'
import { SectionHeading } from './section-heading'

const STEPS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: FilePen,
    title: 'Build',
    body: 'Start from scratch or import your PDF or DOCX. Every template is single-column and ATS-safe.',
  },
  {
    icon: ScanSearch,
    title: 'Analyze gaps',
    body: 'Pick a target role. See your ATS score and exactly which skills are missing, most critical first.',
  },
  {
    icon: ShieldCheck,
    title: 'Learn & prove',
    body: 'Follow curated resources, do a small proof project that fits your field, and upload your licence, certificate or work for verification.',
  },
  {
    icon: Briefcase,
    title: 'Get hired',
    body: 'Verified skills go onto your resume with proof links a recruiter can click.',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-y bg-muted/40">
      <div className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-20 sm:px-6 md:py-24 lg:px-8">
        <SectionHeading eyebrow="How it works" title="From “not sure why I'm not hearing back” to hired">
          Four steps, and each one feeds the next. Every skill you prove makes the resume stronger.
        </SectionHeading>

        <ol className="relative grid gap-8 lg:grid-cols-4 lg:gap-6">
          {/* Connecting line: vertical on mobile, horizontal from lg. Draws in on scroll. */}
          <m.span
            aria-hidden
            className="absolute top-7 bottom-7 left-7 w-px origin-top bg-gradient-to-b from-primary/60 via-primary/30 to-highlight/50 lg:hidden"
            initial={{ scaleY: 0 }}
            whileInView={{ scaleY: 1 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          />
          <m.span
            aria-hidden
            className="absolute top-7 right-[12.5%] left-[12.5%] hidden h-px origin-left bg-gradient-to-r from-primary/60 via-primary/30 to-highlight/50 lg:block"
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          />
          {STEPS.map(({ icon: Icon, title, body }, index) => (
            <Reveal key={title} as="li" delay={0.1 + index * 0.12} className="relative flex gap-5 lg:flex-col lg:items-center lg:text-center">
              <span className="relative z-10 flex size-14 shrink-0 items-center justify-center rounded-2xl border bg-card text-primary shadow-sm">
                <Icon className="size-6" aria-hidden />
                <span className="absolute -top-2 -right-2 flex size-6 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
                  {index + 1}
                </span>
              </span>
              <div className="flex flex-col gap-1.5 pt-1.5 lg:pt-0">
                <h3 className="text-h4">{title}</h3>
                <p className="text-sm text-muted-foreground lg:mx-auto lg:max-w-[15rem]">{body}</p>
              </div>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  )
}
