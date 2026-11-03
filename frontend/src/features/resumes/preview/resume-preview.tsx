import { useLayoutEffect, useMemo, useRef, useState } from 'react'

import type { PageSize } from '@/features/auth/types'
import type { ProofLinks } from '@/features/suggestions/types'

import type { ResumeData, ResumeTemplate, ResumeType } from '../types'
import { useSectionCatalog } from '../sections/api'
import { buildDocument } from './document'
import { PAGE_MM, templateCss } from './templates'

// Markup and class names mirror backend/app/services/export/templates/resume.html.j2, and the
// CSS is the very same file the PDF renderer uses, so the preview matches the export.

const mmToPx = (mm: number) => (mm / 25.4) * 96

interface ResumePreviewProps {
  data: ResumeData
  type: ResumeType
  template: ResumeTemplate
  proofLinks?: ProofLinks
  /** 'fit' scales the page to the available width; a number is an explicit zoom (1 = 100%). */
  zoom?: 'fit' | number
  /** Paper look: shadow, and dashed markers where each new page would start. */
  paper?: boolean
  pageSize?: PageSize
}

export function ResumePreview({
  data,
  type,
  template,
  proofLinks,
  zoom = 'fit',
  paper = false,
  pageSize = 'a4',
}: ResumePreviewProps) {
  const page = PAGE_MM[pageSize]
  const pageWidthPx = mmToPx(page.width)
  const pageHeightPx = mmToPx(page.height)
  const catalog = useSectionCatalog().data
  const doc = useMemo(() => buildDocument(data, type, proofLinks, catalog), [data, type, proofLinks, catalog])
  const css = useMemo(() => templateCss(template), [template])
  const { frameRef, paperRef, fit, height } = useFitToWidth(pageWidthPx)
  const scale = zoom === 'fit' ? fit : zoom
  const pages = Math.max(1, Math.ceil((height - 1) / pageHeightPx))

  return (
    <div ref={frameRef} className="w-full">
      <style>{css}</style>
      {/* Reserve the scaled size so nothing overlaps; wider-than-fit zoom scrolls sideways. */}
      <div style={{ height: height * scale, width: pageWidthPx * scale }} className={zoom === 'fit' ? 'overflow-hidden' : 'mx-auto overflow-hidden'}>
        <div
          ref={paperRef}
          // The template class defines --rf-page-margin, so it must sit on the paper itself.
          className={`rf-template-${template} relative origin-top-left bg-white ${
            paper ? 'shadow-[0_1px_2px_rgb(0_0_0/0.06),0_16px_40px_-12px_rgb(0_0_0/0.28)] ring-1 ring-black/5' : 'shadow-sm ring-1 ring-black/5'
          }`}
          style={{
            width: pageWidthPx,
            minHeight: `${page.height}mm`,
            padding: 'var(--rf-page-margin)',
            transform: `scale(${scale})`,
          }}
        >
          {paper &&
            Array.from({ length: pages - 1 }, (_, i) => (
              <div
                key={i}
                aria-hidden
                className="pointer-events-none absolute inset-x-0 border-t-2 border-dashed border-sky-500/40"
                style={{ top: pageHeightPx * (i + 1) }}
              >
                <span className="absolute -top-3 right-3 rounded-full bg-sky-500/10 px-2 py-0.5 font-sans text-[11px] font-medium text-sky-700">
                  Page {i + 2}
                </span>
              </div>
            ))}
          <article
            aria-label="Resume preview"
            className={`rf-resume rf-template-${template}`}
          >
            <div className="rf-identity">
              {doc.name ? (
                <h1 className="rf-name">{doc.name}</h1>
              ) : (
                <h1 className="rf-name" style={{ color: '#9ca3af' }}>
                  Your Name
                </h1>
              )}
              {doc.headline && <p className="rf-headline">{doc.headline}</p>}
              {doc.contact.length > 0 && <p className="rf-contact">{doc.contact.join(' | ')}</p>}
            </div>
            {doc.sections.map((section) => (
              <section key={section.key} className="rf-section">
                <h2 className="rf-heading">{section.heading}</h2>
                {section.text && <p className="rf-text">{section.text}</p>}
                {section.extra.map((line) => (
                  <p key={line} className="rf-text">{line}</p>
                ))}
                {section.entries.map((entry, i) => (
                  <div key={i} className="rf-entry">
                    <div className="rf-entry-head">
                      <span className="rf-entry-title">{entry.title}</span>
                      {entry.date && <span className="rf-entry-date">{entry.date}</span>}
                    </div>
                    {entry.subtitle && <p className="rf-entry-sub">{entry.subtitle}</p>}
                    {entry.link && <p className="rf-entry-link">{entry.link}</p>}
                    {entry.description && <p className="rf-text">{entry.description}</p>}
                    {entry.bullets.length > 0 && (
                      <ul className="rf-bullets">
                        {entry.bullets.map((bullet, j) => (
                          <li key={j}>{bullet}</li>
                        ))}
                      </ul>
                    )}
                    {entry.tools.length > 0 && (
                      <p className="rf-tools">Tools: {entry.tools.join(', ')}</p>
                    )}
                  </div>
                ))}
                {section.items.length > 0 && (
                  <ul className="rf-bullets">
                    {section.items.map((item, j) => (
                      <li key={j}>{item}</li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </article>
        </div>
      </div>
    </div>
  )
}

/** Scale a real-size page down to the available width, keeping identical line breaks. */
function useFitToWidth(pageWidthPx: number) {
  const frameRef = useRef<HTMLDivElement>(null)
  const paperRef = useRef<HTMLDivElement>(null)
  const [fit, setFit] = useState(1)
  const [height, setHeight] = useState(0)

  useLayoutEffect(() => {
    const frame = frameRef.current
    const paper = paperRef.current
    if (!frame || !paper) return
    const observer = new ResizeObserver(() => {
      setFit(Math.min(1, frame.clientWidth / pageWidthPx))
      setHeight(paper.offsetHeight)
    })
    observer.observe(frame)
    observer.observe(paper)
    return () => observer.disconnect()
  }, [pageWidthPx])

  return { frameRef, paperRef, fit, height }
}
