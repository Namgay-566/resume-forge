import { CheckCircle2, FileUp, Loader2, Upload } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { cn } from '@/lib/utils'
import { notifySuccess } from '@/lib/notify'

import { useImportResume } from './api'
import type { ImportedState } from './types'

const MAX_BYTES = 5 * 1024 * 1024
const ACCEPT = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

type Phase = 'idle' | 'uploading' | 'analysing' | 'done'

function checkFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!name.endsWith('.pdf') && !name.endsWith('.docx')) {
    return name.endsWith('.doc')
      ? 'Old .doc files aren’t supported. Save it as .docx or PDF and try again.'
      : 'Upload a PDF or Word (.docx) file.'
  }
  if (file.size > MAX_BYTES) return 'That file is over 5 MB. Upload a smaller PDF or DOCX.'
  if (file.size === 0) return 'That file is empty.'
  return null
}

export function ImportResumeDialog({ defaultOpen = false }: { defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const [phase, setPhase] = useState<Phase>('idle')
  const [progress, setProgress] = useState(0)
  const [fileName, setFileName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const importResume = useImportResume()
  const navigate = useNavigate()
  const busy = phase === 'uploading' || phase === 'analysing'

  const reset = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setPhase('idle')
    setProgress(0)
    setFileName(null)
    setError(null)
    setDragging(false)
  }

  const start = async (file: File) => {
    setError(null)
    const problem = checkFile(file)
    if (problem) {
      setError(problem)
      return
    }
    const controller = new AbortController()
    abortRef.current = controller
    setFileName(file.name)
    setProgress(0)
    setPhase('uploading')
    try {
      const result = await importResume.mutateAsync({
        file,
        signal: controller.signal,
        onUploadProgress: (fraction) => {
          setProgress(fraction)
          // The upload is done; the server is now extracting and analysing.
          if (fraction >= 1) setPhase('analysing')
        },
      })
      setPhase('done')
      const state: ImportedState = {
        imported: {
          fileName: file.name,
          matchedSkills: result.matched_skills,
          unmatchedSkills: result.unmatched_skills,
        },
      }
      setOpen(false)
      notifySuccess('Resume imported', 'Check each section, then fill in anything we missed.')
      navigate(`/resumes/${result.resume.id}`, { state })
    } catch (err) {
      if (controller.signal.aborted) return
      setPhase('idle')
      setError(apiErrorMessage(err, {}, { useServerDetail: true }))
    } finally {
      abortRef.current = null
    }
  }

  const onDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file && !busy) void start(file)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline">
          <FileUp />
          Import resume
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import a resume</DialogTitle>
          <DialogDescription>
            Upload your current resume and we'll turn it into an editable one. You can fix anything
            afterwards.
          </DialogDescription>
        </DialogHeader>

        {busy || phase === 'done' ? (
          <ImportProgress phase={phase} progress={progress} fileName={fileName ?? ''} />
        ) : (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              'flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
              dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-foreground/30',
            )}
          >
            <Upload className="size-8 text-muted-foreground" />
            <span className="font-medium">
              {dragging ? 'Drop to upload' : 'Drag your resume here, or click to browse'}
            </span>
            <span className="text-sm text-muted-foreground">PDF or DOCX, up to 5 MB</span>
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-label="Resume file"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = '' // allow picking the same file again after an error
            if (file) void start(file)
          }}
        />

        <FormError message={error} />
        {busy && (
          <Button variant="ghost" onClick={reset} className="self-end">
            Cancel
          </Button>
        )}
      </DialogContent>
    </Dialog>
  )
}

function ImportProgress({ phase, progress, fileName }: { phase: Phase; progress: number; fileName: string }) {
  const steps = [
    { key: 'uploading', label: phase === 'uploading' ? `Uploading ${Math.round(progress * 100)}%` : 'Uploaded' },
    { key: 'analysing', label: 'Reading and organising your resume' },
    { key: 'done', label: 'Opening the editor' },
  ] as const
  const order: Phase[] = ['uploading', 'analysing', 'done']
  const current = order.indexOf(phase)

  return (
    <div className="flex flex-col gap-4 rounded-xl border px-5 py-5" aria-live="polite">
      <p className="truncate text-sm font-medium">{fileName}</p>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label="Import progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={phase === 'uploading' ? Math.round(progress * 100) : undefined}
      >
        <div
          className={cn(
            'h-full rounded-full bg-primary transition-[width] duration-300',
            phase === 'analysing' && 'animate-pulse',
          )}
          style={{ width: phase === 'uploading' ? `${Math.max(5, progress * 60)}%` : phase === 'analysing' ? '80%' : '100%' }}
        />
      </div>
      <ol className="flex flex-col gap-2 text-sm">
        {steps.map((step, index) => (
          <li
            key={step.key}
            className={cn('flex items-center gap-2', index > current && 'text-muted-foreground')}
          >
            {index < current || phase === 'done' ? (
              <CheckCircle2 className="size-4 text-success-text" />
            ) : index === current ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <span className="size-4 rounded-full border" />
            )}
            {step.label}
          </li>
        ))}
      </ol>
      {phase === 'analysing' && (
        <p className="text-xs text-muted-foreground">This usually takes 10–40 seconds.</p>
      )}
    </div>
  )
}
