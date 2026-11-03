import { zodResolver } from '@hookform/resolvers/zod'
import { isAxiosError } from 'axios'
import { Eye, PenLine } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AtsPanel } from '@/features/ats/ats-panel'
import type { Location } from '@/features/ats/types'
import { useResume, useUpdateResume } from '@/features/resumes/api'
import { scrollToLocation } from '@/features/resumes/editor/anchors'
import { DocumentBar } from '@/features/resumes/editor/document-bar'
import { EditorContext } from '@/features/resumes/editor/editor-context'
import { EditorToolbar } from '@/features/resumes/editor/editor-toolbar'
import { ImportBanner } from '@/features/resumes/editor/import-banner'
import { SectionList } from '@/features/resumes/editor/section-list'
import { PersonalInfoSection } from '@/features/resumes/editor/sections'
import { PreviewPane } from '@/features/resumes/editor/preview-pane'
import { useAutosave } from '@/features/resumes/editor/use-autosave'
import { resumeFormSchema, toFormValues, type ResumeFormValues } from '@/features/resumes/form-schema'
import type { ImportedState, Resume } from '@/features/resumes/types'
import { useResumeSuggestions } from '@/features/suggestions/api'
import { SuggestionsPanel } from '@/features/suggestions/suggestions-panel'
import { TailorPanel } from '@/features/writing/tailor-panel'
import { useDocumentTitle } from '@/lib/use-document-title'

export function ResumeEditorPage() {
  const { resumeId = '' } = useParams()
  const resume = useResume(resumeId)

  if (resume.isPending) return <EditorSkeleton />
  if (resume.isError) {
    const notFound = isAxiosError(resume.error) && resume.error.response?.status === 404
    return (
      <div className="flex flex-col items-start gap-3">
        <h1 className="text-xl font-semibold">{notFound ? 'Resume not found' : 'Could not load resume'}</h1>
        <p className="text-muted-foreground">
          {notFound ? 'It may have been deleted.' : 'Check your connection and try again.'}
        </p>
        <div className="flex gap-2">
          {!notFound && <Button onClick={() => void resume.refetch()}>Retry</Button>}
          <Button asChild variant="outline">
            <Link to="/resumes">Back to My Resumes</Link>
          </Button>
        </div>
      </div>
    )
  }
  // Keyed so switching resumes starts a fresh form instead of reusing the old one.
  return <ResumeEditor key={resume.data.id} resume={resume.data} />
}

function ResumeEditor({ resume }: { resume: Resume }) {
  const defaultValues = useMemo(() => toFormValues(resume), [resume])
  const form = useForm<ResumeFormValues>({
    defaultValues,
    resolver: zodResolver(resumeFormSchema),
    mode: 'onChange',
  })
  const update = useUpdateResume(resume.id)
  const { status, savedAt, saveNow } = useAutosave(form, update.mutateAsync)
  const imported = (useLocation().state as ImportedState | null)?.imported
  const [tab, setTab] = useState<'edit' | 'preview'>('edit')
  // The dashboard links here with ?ats=open to jump straight into the ATS check.
  const [searchParams] = useSearchParams()
  const [atsOpen, setAtsOpen] = useState(() => searchParams.get('ats') === 'open')
  const lastSavedAt = savedAt ?? new Date(resume.updated_at)
  useDocumentTitle(useWatch({ control: form.control, name: 'title' }) || 'Resume editor')

  // One toast per failed save (the toolbar also shows it); invalid fields are shown inline.
  useEffect(() => {
    if (status !== 'error') return
    toast.error('Your latest changes aren’t saved yet', {
      id: 'autosave-error',
      description: 'Check your connection. We’ll try again when you keep editing.',
      action: { label: 'Retry', onClick: () => void saveNow() },
    })
  }, [status, saveNow])

  const jumpTo = useCallback((location: Location) => {
    setAtsOpen(false)
    setTab('edit') // on small screens the form may be behind the Preview tab
    // Wait for the sheet to close and the edit pane to show before scrolling.
    window.setTimeout(() => scrollToLocation(location), 320)
  }, [])

  const suggestions = useResumeSuggestions(resume.id)
  const proofLinks = suggestions.data?.proof_links
  const editorContext = useMemo(
    () => ({ resumeId: resume.id, saveNow, proofLinks: proofLinks ?? {} }),
    [resume.id, saveNow, proofLinks],
  )

  return (
    <EditorContext.Provider value={editorContext}>
      <FormProvider {...form}>
        <form onSubmit={(event) => event.preventDefault()} noValidate className="-mt-6 flex flex-col gap-5 md:-mt-8">
          <EditorToolbar
            resumeId={resume.id}
            status={status}
            savedAt={savedAt}
            onRetry={() => void saveNow()}
            saveNow={saveNow}
            atsPanel={(trigger) => (
              <AtsPanel
                resumeId={resume.id}
                open={atsOpen}
                onOpenChange={setAtsOpen}
                saveNow={saveNow}
                lastSavedAt={lastSavedAt}
                onJump={jumpTo}
                trigger={trigger}
              />
            )}
            extra={<TailorPanel />}
          />
          {imported && <ImportBanner imported={imported} />}
          <SuggestionsPanel resumeId={resume.id} saveStatus={status} />

          {/* Tabs on small screens; side by side from lg up (both panes stay mounted). */}
          <Tabs value={tab} onValueChange={(value) => setTab(value as 'edit' | 'preview')} className="gap-4">
            <TabsList className="grid w-full grid-cols-2 lg:hidden">
              <TabsTrigger value="edit">
                <PenLine /> Edit
              </TabsTrigger>
              <TabsTrigger value="preview">
                <Eye /> Preview
              </TabsTrigger>
            </TabsList>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
              <TabsContent value="edit" forceMount tabIndex={-1} className="flex flex-col gap-4 data-[state=inactive]:hidden lg:data-[state=inactive]:flex">
                <a
                  href="#preview-heading"
                  className="sr-only rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only focus:self-start"
                  onClick={() => setTab('preview')}
                >
                  Skip to preview
                </a>
                <DocumentBar />
                <PersonalInfoSection />
                <SectionList />
              </TabsContent>
              <TabsContent
                value="preview"
                forceMount
                // The panes aren't tab stops: focus goes straight to their first control.
                tabIndex={-1}
                className="data-[state=inactive]:hidden lg:sticky lg:top-[8.5rem] lg:h-[calc(100svh-9.5rem)] lg:data-[state=inactive]:block"
              >
                <PreviewPane />
              </TabsContent>
            </div>
          </Tabs>
        </form>
      </FormProvider>
    </EditorContext.Provider>
  )
}

function EditorSkeleton() {
  return (
    <div className="-mt-6 flex flex-col gap-5 md:-mt-8" aria-busy="true" aria-label="Loading resume">
      <div className="-mx-4 flex items-center gap-3 border-b px-4 py-3 md:-mx-8 md:px-8">
        <Skeleton className="size-8 rounded-md" />
        <Skeleton className="h-6 w-56" />
        <Skeleton className="ml-auto h-8 w-72 max-w-[40%] rounded-md" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Skeleton className="h-36 rounded-2xl" />
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3 rounded-2xl border p-4">
              <Skeleton className="size-9 rounded-xl" />
              <div className="flex flex-1 flex-col gap-1.5">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-24" />
              </div>
              <Skeleton className="size-6 rounded-full" />
            </div>
          ))}
        </div>
        <div className="hidden rounded-2xl border bg-muted/70 p-6 lg:block">
          <Skeleton className="mx-auto aspect-[210/297] w-full max-w-xl rounded-sm bg-card" />
        </div>
      </div>
    </div>
  )
}
