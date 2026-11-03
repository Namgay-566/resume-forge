import { AlertCircle, ArrowLeft, Check, ChevronDown, CloudUpload, Download, FileText, FileType, LayoutTemplate, Loader2 } from 'lucide-react'
import { forwardRef, useMemo, useState, type ComponentProps, type ReactNode } from 'react'
import { useFormContext, useWatch } from 'react-hook-form'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useLatestAnalysis } from '@/features/ats/api'
import { apiErrorMessage } from '@/features/auth/api-error'
import { atsBand } from '@/features/dashboard/status'
import { findPlaceholders } from '@/features/writing/diff'
import { cn } from '@/lib/utils'

import { downloadResume, type ExportFormat } from '../export'
import { toResumeData, type ResumeFormValues } from '../form-schema'
import { ResumePreview } from '../preview/resume-preview'
import { TEMPLATES } from '../preview/templates'
import { useTargetRoles } from '@/features/target-roles/api'
import type { ResumeTemplate } from '../types'
import type { SaveStatus } from './use-autosave'

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })

interface EditorToolbarProps {
  resumeId: string
  status: SaveStatus
  savedAt: Date | null
  onRetry: () => void
  saveNow: () => Promise<boolean>
  /** ATS panel (rendered with our badge as its trigger) and other panels. */
  atsPanel: (trigger: ReactNode) => ReactNode
  extra?: ReactNode
}

/** Sticky editor toolbar: back, title, save state | template, ATS, extras, download. */
export function EditorToolbar({ resumeId, status, savedAt, onRetry, saveNow, atsPanel, extra }: EditorToolbarProps) {
  const { register, formState } = useFormContext<ResumeFormValues>()
  const titleError = formState.errors.title

  return (
    <div className="sticky top-14 z-20 -mx-4 border-b bg-background/85 px-4 py-2.5 backdrop-blur-md md:-mx-8 md:px-8">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="flex min-w-0 flex-1 basis-72 items-center gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild variant="ghost" size="icon-sm" className="-ml-1.5">
                <Link to="/resumes" aria-label="Back to My Resumes">
                  <ArrowLeft />
                </Link>
              </Button>
            </TooltipTrigger>
            <TooltipContent>My Resumes</TooltipContent>
          </Tooltip>
          <div className="min-w-0 flex-1">
            {/* The page's heading (the resume preview's name heading is hidden on small screens). */}
            <h1 className="sr-only">Resume editor</h1>
            <label htmlFor="title" className="sr-only">
              Resume name
            </label>
            <input
              id="title"
              aria-invalid={titleError ? true : undefined}
              aria-describedby={titleError ? 'title-error' : undefined}
              className="h-9 w-full min-w-0 truncate rounded-lg border border-transparent bg-transparent px-2 font-heading text-lg font-semibold tracking-tight transition-colors outline-none hover:border-input focus-visible:border-ring focus-visible:bg-card focus-visible:ring-3 focus-visible:ring-ring/20 aria-invalid:border-danger"
              {...register('title')}
            />
            {titleError && (
              <p id="title-error" className="px-2 text-xs text-danger-text">
                {titleError.message}
              </p>
            )}
          </div>
          <SaveIndicator status={status} savedAt={savedAt} onRetry={onRetry} />
        </div>
        <div className="flex items-center gap-2">
          <TemplatePicker />
          {atsPanel(<AtsBadge resumeId={resumeId} />)}
          {extra}
          <DownloadMenu resumeId={resumeId} saveNow={saveNow} />
        </div>
      </div>
    </div>
  )
}

// --- Save state -------------------------------------------------------------------------

function SaveIndicator({ status, savedAt, onRetry }: { status: SaveStatus; savedAt: Date | null; onRetry: () => void }) {
  return (
    <div role="status" aria-live="polite" className="flex shrink-0 items-center gap-1.5 text-xs font-medium whitespace-nowrap">
      {status === 'saved' && (
        <span className="flex items-center gap-1.5 text-muted-foreground" title={savedAt ? `Saved at ${timeFormat.format(savedAt)}` : undefined}>
          <span className="flex size-4 items-center justify-center rounded-full bg-success-muted text-success-text">
            <Check className="size-3" strokeWidth={3} aria-hidden />
          </span>
          Saved
        </span>
      )}
      {status === 'pending' && (
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <CloudUpload className="size-4" aria-hidden /> Unsaved
        </span>
      )}
      {status === 'saving' && (
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Saving…
        </span>
      )}
      {status === 'invalid' && (
        <span className="flex items-center gap-1.5 text-danger-text">
          <AlertCircle className="size-4" aria-hidden /> Fix highlighted fields
        </span>
      )}
      {status === 'error' && (
        <span className="flex items-center gap-1 text-danger-text">
          <AlertCircle className="size-4" aria-hidden /> Not saved
          <Button variant="link" size="sm" className="h-auto px-1 text-xs" onClick={onRetry}>
            Retry
          </Button>
        </span>
      )}
    </div>
  )
}

// --- Template picker -----------------------------------------------------------------------

function TemplatePicker() {
  const { control, setValue } = useFormContext<ResumeFormValues>()
  const template = useWatch({ control, name: 'template' })
  const roleId = useWatch({ control, name: 'target_role_id' })
  const [open, setOpen] = useState(false)
  const current = TEMPLATES.find((t) => t.value === template)
  // The template suited to the target role's field.
  const industry = useTargetRoles().data?.find((r) => r.id === roleId)?.industry
  const recommended = industry?.recommended_template

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="sm" aria-label={`Template: ${current?.label}. Change template`}>
          <LayoutTemplate />
          <span className="hidden sm:inline">{current?.label}</span>
          <ChevronDown className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" aria-label="Choose a template" className="w-[min(94vw,27rem)] gap-3 p-3">
        <p className="px-1 text-sm font-semibold">Template</p>
        {/* Thumbnails are your own resume in each template, rendered with the real PDF styles. */}
        <div role="radiogroup" aria-label="Template" className="grid grid-cols-3 gap-2.5">
          {open &&
            TEMPLATES.map((option) => (
              <TemplateCard
                key={option.value}
                value={option.value}
                label={option.label}
                description={`${option.description}. Suits ${option.suits.toLowerCase()}`}
                recommended={option.value === recommended ? industry?.name : undefined}
                selected={option.value === template}
                onSelect={() => {
                  setValue('template', option.value, { shouldDirty: true })
                  setOpen(false)
                }}
              />
            ))}
        </div>
        <p className="px-1 text-xs text-muted-foreground">
          All templates are single-column and ATS-safe.
          {industry && current?.value !== recommended && ` ${TEMPLATES.find((t) => t.value === recommended)?.label} is recommended for ${industry.name}.`}
        </p>
      </PopoverContent>
    </Popover>
  )
}

interface TemplateCardProps {
  value: ResumeTemplate
  label: string
  description: string
  /** The field it's recommended for, when it is. */
  recommended?: string
  selected: boolean
  onSelect: () => void
}

function TemplateCard({ value, label, description, recommended, selected, onSelect }: TemplateCardProps) {
  const values = useWatch<ResumeFormValues>() as ResumeFormValues
  const data = useMemo(() => toResumeData(values), [values])
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-label={`${label}${recommended ? ` (recommended for ${recommended})` : ''}: ${description}`}
      onClick={onSelect}
      className={cn(
        'group flex flex-col gap-2 rounded-xl border-2 p-1.5 text-left transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/40',
        selected ? 'border-primary bg-secondary' : 'border-transparent hover:border-border hover:bg-muted',
      )}
    >
      <div aria-hidden className="pointer-events-none aspect-[210/297] w-full overflow-hidden rounded-md ring-1 ring-black/10">
        <ResumePreview data={data} type={values.type} template={value} />
      </div>
      <span className="flex items-center justify-between gap-1 px-0.5">
        <span className="text-xs font-semibold">{label}</span>
        {selected && <Check className="size-3.5 text-primary" aria-hidden />}
      </span>
      {recommended && (
        <span className="px-0.5 text-[11px] font-medium text-highlight-text" aria-hidden>
          Recommended
        </span>
      )}
    </button>
  )
}

// --- ATS badge -------------------------------------------------------------------------------

/** Latest ATS score as a compact badge. Opens the ATS panel (rendered as its trigger). */
const AtsBadge = forwardRef<HTMLButtonElement, ComponentProps<'button'> & { resumeId: string }>(function AtsBadge(
  { resumeId, className, ...props },
  ref,
) {
  const latest = useLatestAnalysis(resumeId, true)
  const score = latest.data?.score ?? null
  const band = score === null ? null : atsBand(score)
  const color = band ? `var(--${band.tone})` : 'var(--muted-foreground)'
  const r = 9
  const c = 2 * Math.PI * r
  return (
    <button
      ref={ref}
      type="button"
      aria-label={score === null ? 'ATS score: not checked yet. Open ATS check' : `ATS score ${score} of 100, ${band?.label}. Open ATS check`}
      className={cn(
        'inline-flex h-8 items-center gap-2 rounded-full border bg-card pr-3 pl-1 text-sm font-medium shadow-xs transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/40',
        className,
      )}
      {...props}
    >
      <svg width="24" height="24" viewBox="0 0 24 24" className="-rotate-90" aria-hidden>
        <circle cx="12" cy="12" r={r} fill="none" strokeWidth="3" className="stroke-muted" />
        {score !== null && (
          <circle cx="12" cy="12" r={r} fill="none" strokeWidth="3" strokeLinecap="round" stroke={color} strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)} />
        )}
      </svg>
      {score === null ? (
        <span>
          ATS <span className="text-muted-foreground">· Check</span>
        </span>
      ) : (
        <span className="tabular-nums">
          ATS <span className="font-semibold">{score}</span>
        </span>
      )}
    </button>
  )
})

// --- Download ---------------------------------------------------------------------------------

const FORMATS: { format: ExportFormat; label: string; hint: string; icon: typeof FileText }[] = [
  { format: 'pdf', label: 'PDF', hint: 'Best for applying online', icon: FileText },
  { format: 'docx', label: 'Word (DOCX)', hint: 'When a recruiter asks for Word', icon: FileType },
]

function DownloadMenu({ resumeId, saveNow }: { resumeId: string; saveNow: () => Promise<boolean> }) {
  const { getValues } = useFormContext<ResumeFormValues>()
  const [busy, setBusy] = useState<ExportFormat | null>(null)

  const onDownload = async (format: ExportFormat) => {
    setBusy(format)
    try {
      // 1. NEW: Check for placeholders before saving or downloading
      const data = getValues('data')
      const placeholders = findPlaceholders(JSON.stringify(data))
      
      if (placeholders.length > 0) {
        toast.error('Please fill in all placeholders first.', {
          description: `Found ${placeholders.length} placeholders like ${placeholders[0]} in your resume. Replace them with your real numbers.`,
          duration: 6000,
        })
        return // Stop the download
      }

      // 2. Proceed with the existing save and download logic
      if (!(await saveNow())) {
        toast.error('Fix the highlighted fields before downloading.')
        return
      }
      await downloadResume(resumeId, format, getValues('template'))
      toast.success(`${format.toUpperCase()} downloaded`)
    } catch (err) {
      toast.error('Download failed', { description: apiErrorMessage(err) })
    } finally {
      setBusy(null)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" size="sm" disabled={busy !== null} aria-label={busy ? 'Preparing download' : 'Download'}>
          {busy ? <Loader2 className="animate-spin" /> : <Download />}
          <span className="hidden sm:inline">{busy ? 'Preparing…' : 'Download'}</span>
          <ChevronDown className="opacity-70" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Download as</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {FORMATS.map(({ format, label, hint, icon: Icon }) => (
          <DropdownMenuItem key={format} onSelect={() => void onDownload(format)} className="items-start gap-2.5 py-2">
            <Icon className="mt-0.5" />
            <span className="flex flex-col">
              <span className="font-medium">{label}</span>
              <span className="text-xs text-muted-foreground">{hint}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}