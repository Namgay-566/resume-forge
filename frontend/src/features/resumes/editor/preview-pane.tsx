import { Maximize, Minus, Plus } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { useWatch } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useAuth } from '@/features/auth/use-auth'

import { toResumeData, type ResumeFormValues } from '../form-schema'
import { ResumePreview } from '../preview/resume-preview'
import { useEditor } from './editor-context'

const STEPS = [0.5, 0.75, 1, 1.25, 1.5]
const ZOOM_KEY = 'rf-preview-zoom'

function readZoom(): 'fit' | number {
  try {
    const value = Number(localStorage.getItem(ZOOM_KEY))
    return STEPS.includes(value) ? value : 'fit'
  } catch {
    return 'fit'
  }
}

/** The live preview as a sheet of A4 paper on a desk, with zoom. */
export function PreviewPane() {
  const [zoom, setZoomState] = useState<'fit' | number>(readZoom)
  const setZoom = (next: 'fit' | number) => {
    setZoomState(next)
    try {
      localStorage.setItem(ZOOM_KEY, String(next))
    } catch {
      // storage blocked: zoom still applies for this visit
    }
  }
  const current = zoom === 'fit' ? null : zoom
  const step = (direction: 1 | -1) => {
    const base = current ?? 0.75 // "Fit" is roughly 75% on a laptop screen
    const next = direction > 0 ? STEPS.find((s) => s > base) : [...STEPS].reverse().find((s) => s < base)
    if (next) setZoom(next)
  }

  return (
    <section aria-labelledby="preview-heading" className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border bg-muted/70">
      <div className="flex items-center justify-between gap-2 border-b bg-card/70 px-3 py-2 backdrop-blur">
        <h2 id="preview-heading" className="px-1 text-sm font-semibold">
          Live preview
        </h2>
        <div className="flex items-center gap-0.5" role="group" aria-label="Zoom">
          <Button type="button" variant="ghost" size="icon-sm" onClick={() => step(-1)} disabled={current === STEPS[0]} aria-label="Zoom out">
            <Minus />
          </Button>
          <span className="w-12 text-center text-xs font-medium tabular-nums" aria-live="polite">
            {zoom === 'fit' ? 'Fit' : `${Math.round(zoom * 100)}%`}
          </span>
          <Button type="button" variant="ghost" size="icon-sm" onClick={() => step(1)} disabled={current === STEPS[STEPS.length - 1]} aria-label="Zoom in">
            <Plus />
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant={zoom === 'fit' ? 'secondary' : 'ghost'}
                size="icon-sm"
                onClick={() => setZoom('fit')}
                aria-label="Fit to width"
                aria-pressed={zoom === 'fit'}
              >
                <Maximize />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Fit to width</TooltipContent>
          </Tooltip>
        </div>
      </div>
      {/* The desk: a faint dot grid behind the paper. */}
      <div
        className="min-h-0 flex-1 overflow-auto p-4 md:p-6"
        style={{ backgroundImage: 'radial-gradient(color-mix(in oklch, var(--foreground) 9%, transparent) 1px, transparent 1px)', backgroundSize: '16px 16px' }}
      >
        <LivePreview zoom={zoom} />
      </div>
    </section>
  )
}

function LivePreview({ zoom }: { zoom: 'fit' | number }) {
  // Defaults are complete, so watched values always have the full shape.
  const values = useWatch<ResumeFormValues>() as ResumeFormValues
  // Keep typing responsive: the preview may lag a frame behind the form.
  const deferred = useDeferredValue(values)
  const data = useMemo(() => toResumeData(deferred), [deferred])
  const { proofLinks } = useEditor()
  const pageSize = useAuth().user?.preferences.page_size
  return (
    <ResumePreview
      data={data}
      type={deferred.type}
      template={deferred.template}
      proofLinks={proofLinks}
      zoom={zoom}
      paper
      pageSize={pageSize}
    />
  )
}
