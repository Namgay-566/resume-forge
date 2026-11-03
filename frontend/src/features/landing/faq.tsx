import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'

import { Reveal } from './motion'
import { SectionHeading } from './section-heading'

const FAQS = [
  {
    q: 'What is an ATS, and why does it matter?',
    a: 'An applicant tracking system reads and ranks resumes before a person does. Tables, columns, images and unusual headings can scramble what it sees. Every ResumeForge template is single-column with standard headings and real, selectable text, in both PDF and DOCX.',
  },
  {
    q: 'How is my ATS score calculated?',
    a: 'With checks you can see: sections, contact details, dates, bullet length, action verbs, measurable results, and keywords from the job description or your target role. Each suggested fix tells you how many points it is worth. An AI recruiter-style review adds feedback, but it never changes the score.',
  },
  {
    q: 'How does skill verification work?',
    a: 'Upload the proof that fits your field: a professional licence, a certificate, a work sample (a lesson plan, a campaign, a care plan, a design), a portfolio link, a publication, or a reference letter. Code repositories work for technical roles. An AI reviewer who knows your field looks at the work, and we check licences on the public register and certificates on the issuer’s own page. Every proof gets an honest level: Verified, Partially verified, or Self-reported.',
  },
  {
    q: 'Will the AI make things up on my resume?',
    a: 'No. Suggestions are built from what you wrote. Any number that isn’t in your own text becomes a placeholder like [X%] for you to fill in, and learning recommendations come from a curated list, never invented links.',
  },
  {
    q: 'Can I start from the resume I already have?',
    a: 'Yes. Import a PDF or DOCX and it’s turned into editable sections you can review before anything is saved. Scanned PDFs need a text layer, so export a text PDF or use the DOCX.',
  },
  {
    q: 'Which roles can I target?',
    a: 'Almost any job. There are around a hundred ready-made roles across 16 fields, including healthcare, education, finance, marketing, sales, design, engineering, hospitality, the skilled trades, law, government, research, customer service, operations, HR and technology. Each has weighted required skills, including the licences it needs. If yours isn’t listed, type the job title and we build a profile for it.',
  },
  {
    q: 'I’m a student, or changing careers. Is it for me?',
    a: 'Yes. Choose your career stage and the score, sections and advice adapt: students lead with education, projects, internships and volunteering, and career changers get help showing the transferable skills from their earlier work.',
  },
]

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-20">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 md:py-28 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16 lg:px-8">
        <SectionHeading eyebrow="FAQ" title="Questions, answered" align="left" className="lg:sticky lg:top-28 lg:self-start">
          The short version: honest scores, real proof, and nothing invented on your behalf.
        </SectionHeading>
        <Reveal delay={0.1}>
          <Accordion type="single" collapsible defaultValue="item-0" className="rounded-2xl border bg-card px-5 shadow-xs sm:px-7">
            {FAQS.map(({ q, a }, i) => (
              <AccordionItem key={q} value={`item-${i}`}>
                <AccordionTrigger>{q}</AccordionTrigger>
                <AccordionContent>{a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </Reveal>
      </div>
    </section>
  )
}
