// The same CSS files the backend uses to render PDFs (see vite.config.ts alias).
import academicCss from '@resume-templates/academic.css?raw'
import baseCss from '@resume-templates/base.css?raw'
import classicCss from '@resume-templates/classic.css?raw'
import compactCss from '@resume-templates/compact.css?raw'
import conservativeCss from '@resume-templates/conservative.css?raw'
import modernMinimalCss from '@resume-templates/modern_minimal.css?raw'
import professionalCss from '@resume-templates/professional.css?raw'

import type { PageSize } from '@/features/auth/types'

import type { ResumeTemplate } from '../types'

export interface TemplateOption {
  value: ResumeTemplate
  label: string
  description: string
  /** Who it suits, e.g. "Finance, law, government". */
  suits: string
}

export const TEMPLATES: TemplateOption[] = [
  { value: 'classic', label: 'Classic', description: 'Serif, centred header, ruled headings', suits: 'Healthcare, education, trades' },
  { value: 'conservative', label: 'Conservative', description: 'Understated serif, double-ruled headings', suits: 'Finance, law, government' },
  { value: 'professional', label: 'Professional', description: 'Clean sans-serif with navy headings', suits: 'Business, marketing, sales' },
  { value: 'modern_minimal', label: 'Modern-Minimal', description: 'Clean sans-serif with lots of space', suits: 'Design, technology' },
  { value: 'academic', label: 'Academic CV', description: 'Long format for publications and teaching', suits: 'Research, academia' },
  { value: 'compact', label: 'Compact', description: 'Small type, fits more on one page', suits: 'Any field' },
]

const THEME_CSS: Record<ResumeTemplate, string> = {
  classic: classicCss,
  modern_minimal: modernMinimalCss,
  compact: compactCss,
  conservative: conservativeCss,
  professional: professionalCss,
  academic: academicCss,
}

export function templateCss(template: ResumeTemplate): string {
  return `${baseCss}\n${THEME_CSS[template]}`
}

/** Paper in mm, as in the export (Settings > Resume defaults > Page size). */
export const PAGE_MM: Record<PageSize, { width: number; height: number }> = {
  a4: { width: 210, height: 297 },
  letter: { width: 215.9, height: 279.4 },
}
