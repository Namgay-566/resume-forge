import { FilePlus2 } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { useDeleteResume, useDuplicateResume, useResumes } from '@/features/resumes/api'
import { CreateResumeDialog } from '@/features/resumes/create-resume-dialog'
import { ImportResumeDialog } from '@/features/resumes/import-resume-dialog'
import { ResumeCard } from '@/features/resumes/resume-card'
import { notifyError, notifySuccess } from '@/lib/notify'

export function ResumesPage() {
  const resumes = useResumes()
  const duplicate = useDuplicateResume()
  const remove = useDeleteResume()
  const busy = duplicate.isPending || remove.isPending
  // The landing page links here with ?new=1 or ?import=1 to open the matching dialog.
  const [params] = useSearchParams()
  const [openOnLoad] = useState(() => ({ create: params.has('new'), import: params.has('import') }))

  const onDuplicate = (id: string) => {
    duplicate.mutate(id, {
      onSuccess: (copy) => notifySuccess('Resume duplicated', `“${copy.title}” is ready to edit.`),
      onError: (error) => notifyError('Couldn’t duplicate the resume', error, { 404: 'That resume no longer exists.' }),
    })
  }

  const onDelete = async (id: string) => {
    try {
      await remove.mutateAsync(id)
      notifySuccess('Resume deleted')
    } catch (error) {
      notifyError('Couldn’t delete the resume', error, { 404: 'It was already deleted.' })
    }
  }

  const hasResumes = Boolean(resumes.data && resumes.data.length > 0)

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <PageHeader
        title="My Resumes"
        description="One resume per target role works best."
        actions={
          hasResumes && (
            <>
              <ImportResumeDialog defaultOpen={openOnLoad.import} />
              <CreateResumeDialog defaultOpen={openOnLoad.create} />
            </>
          )
        }
      />

      {resumes.isPending && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading resumes">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex flex-col gap-3 rounded-2xl border p-5">
              <div className="flex gap-3">
                <Skeleton className="size-10 rounded-xl" />
                <div className="flex flex-1 flex-col gap-2">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
              <Skeleton className="h-5 w-32 rounded-full" />
            </li>
          ))}
        </ul>
      )}

      {resumes.isError && (
        <div className="flex flex-col items-start gap-3">
          <FormError message={apiErrorMessage(resumes.error)} />
          <Button variant="outline" onClick={() => void resumes.refetch()}>
            Try again
          </Button>
        </div>
      )}

      {resumes.data?.length === 0 && (
        <Card className="px-5">
          <EmptyState
            icon={FilePlus2}
            title="No resumes yet. Build your first one."
            description="Start from scratch, or import the resume you already have (PDF or DOCX)."
            actions={
              <>
                <CreateResumeDialog defaultOpen={openOnLoad.create} />
                <ImportResumeDialog defaultOpen={openOnLoad.import} />
              </>
            }
          />
        </Card>
      )}

      {hasResumes && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {resumes.data!.map((resume) => (
            <ResumeCard key={resume.id} resume={resume} busy={busy} onDuplicate={onDuplicate} onDelete={onDelete} />
          ))}
        </ul>
      )}
    </div>
  )
}
