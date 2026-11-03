import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useFormContext } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { apiErrorMessage } from '@/features/auth/api-error'
import { useEditor } from '@/features/resumes/editor/editor-context'
import type { ResumeFormValues } from '@/features/resumes/form-schema'
import { notifySuccess } from '@/lib/notify'

import { useGenerateSummary } from './api'
import { OptionsList } from './options-list'

export function SummaryGenerate() {
  const { resumeId, saveNow } = useEditor()
  const { setValue, getValues } = useFormContext<ResumeFormValues>()
  const generate = useGenerateSummary(resumeId)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setError(null)
    // The summary is written from the saved resume, so save pending edits first.
    if (!(await saveNow())) {
      setError('Fix the highlighted fields first so the AI sees your latest resume.')
      return
    }
    generate.mutate(undefined, {
      onError: (err) => setError(apiErrorMessage(err, {}, { useServerDetail: true })),
    })
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) void run()
      }}
    >
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="sm" className="self-start">
          <Sparkles />
          Generate summary
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="flex w-[min(92vw,30rem)] flex-col gap-3">
        <div>
          <p className="text-sm font-medium">Summary options</p>
          <p className="text-xs text-muted-foreground">
            Written from your resume for your target role. Nothing is invented.
          </p>
        </div>
        <OptionsList
          pending={generate.isPending}
          error={error}
          options={generate.data}
          loadingText="Writing two options…"
          onUse={(option) => {
            setValue('data.summary', option.text, { shouldDirty: true, shouldValidate: true })
            notifySuccess('Summary updated')
            setOpen(false)
          }}
        />
        {getValues('data.summary').trim() && generate.data && (
          <p className="text-xs text-muted-foreground">“Use this” replaces your current summary.</p>
        )}
        {!generate.isPending && (generate.data || error) && (
          <Button type="button" variant="ghost" size="sm" className="self-end" onClick={() => void run()}>
            Try again
          </Button>
        )}
      </PopoverContent>
    </Popover>
  )
}
