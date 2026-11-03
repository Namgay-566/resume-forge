import { Loader2, RefreshCw, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { useFormContext } from 'react-hook-form'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useEditor } from '@/features/resumes/editor/editor-context'
import type { ResumeFormValues } from '@/features/resumes/form-schema'

import { useImproveBullet } from './api'
import { bulletContext } from './bullet-context'
import { OptionCards } from './option-cards'

interface BulletImproveProps {
  /** The row list the bullet is in, e.g. "data.sections.3.entries.0.bullets". */
  name: string
  bulletIndex: number
  label: string
}

export function BulletImprove({ name, bulletIndex, label }: BulletImproveProps) {
  const { resumeId } = useEditor()
  const { getValues, setValue } = useFormContext<ResumeFormValues>()
  const improve = useImproveBullet(resumeId)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [original, setOriginal] = useState('')
  const [selected, setSelected] = useState(0)
  const path = `${name}.${bulletIndex}.value` as 'data.achievements.0.value'
  const options = improve.data

  const run = () => {
    const text = (getValues(path) ?? '').trim()
    setError(null)
    setSelected(0)
    setOriginal(text)
    if (text.length < 3) {
      setError('Write a rough version of this bullet first, then improve it.')
      return
    }
    const context = bulletContext(getValues('data'), name, bulletIndex)
    if (!context) return
    const { path: _path, ...input } = context
    improve.mutate({ text, ...input }, { onError: (err) => setError(apiErrorMessage(err, {}, { useServerDetail: true })) })
  }

  const accept = () => {
    const option = options?.[selected]
    if (!option) return
    const before = original
    setValue(path, option.text, { shouldDirty: true, shouldValidate: true })
    setOpen(false)
    toast.success('Bullet updated', {
      description: option.placeholders.length ? `Fill in ${option.placeholders.join(', ')} with your real number.` : undefined,
      action: { label: 'Undo', onClick: () => setValue(path, before, { shouldDirty: true, shouldValidate: true }) },
    })
  }

  const ready = !improve.isPending && !error && options && options.length > 0

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) run()
      }}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={`Improve ${label} with AI`}
              className="text-primary hover:bg-secondary hover:text-secondary-foreground data-[state=open]:bg-secondary"
            >
              <Sparkles />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent>Improve with AI</TooltipContent>
      </Tooltip>
      <PopoverContent
        align="end"
        aria-labelledby={`${path}-improve-title`}
        className="flex max-h-[min(80vh,40rem)] w-[min(94vw,30rem)] flex-col gap-0 overflow-hidden p-0"
        // Focus lands on the selected option once they load (see OptionCards), not the first button.
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <div className="flex items-start gap-3 border-b p-4">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
            <Sparkles className="size-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p id={`${path}-improve-title`} className="font-heading text-base font-semibold">
              Improve this bullet
            </p>
            <p className="text-xs text-muted-foreground">Action + what + how + result. Numbers are never made up.</p>
          </div>
          <Button type="button" variant="ghost" size="icon-xs" onClick={() => setOpen(false)} aria-label="Close">
            <X />
          </Button>
        </div>

        <div className="flex min-h-0 flex-col gap-3 overflow-y-auto p-4">
          {original && (
            <div className="rounded-lg bg-muted px-3 py-2">
              <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Your version</p>
              <p className="text-sm">{original}</p>
            </div>
          )}
          {improve.isPending && (
            <div className="flex flex-col gap-2" aria-busy="true">
              <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Writing three stronger versions…
              </p>
              {[0, 1, 2].map((i) => (
                <div key={i} className="flex flex-col gap-2 rounded-xl border-2 p-3">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-4/5" />
                </div>
              ))}
            </div>
          )}
          {error && <FormError message={error} />}
          {!improve.isPending && !error && options?.length === 0 && (
            <p className="text-sm text-muted-foreground">No stronger version found. Add a little more detail, then try again.</p>
          )}
          {ready && (
            <OptionCards
              original={original}
              options={options}
              selected={selected}
              onSelect={setSelected}
              onAccept={accept}
              label="Suggested versions"
            />
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t bg-muted/50 px-4 py-3">
          <Button type="button" variant="ghost" size="sm" onClick={run} disabled={improve.isPending}>
            <RefreshCw /> Try again
          </Button>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
              Reject
            </Button>
            <Button type="button" size="sm" onClick={accept} disabled={!ready}>
              Accept{ready ? ` option ${selected + 1}` : ''}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
