import { Loader2, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { PlaceholderNote } from '@/features/writing/placeholder-text'
import { findPlaceholders } from '@/features/writing/diff'

import { useProjectDraft } from './api'
import type { ProjectDraft } from './types'

export interface ProjectEntry {
  name: string
  description: string
  bullets: string[]
  tools_and_skills: string[]
  link: string
}

interface ProjectDraftDialogProps {
  resumeId: string
  proofId: string | null
  onClose: () => void
  onAccept: (entry: ProjectEntry) => void
}

/** Shows the AI draft as editable fields; nothing is added until the user clicks Add. */
export function ProjectDraftDialog({ resumeId, proofId, onClose, onAccept }: ProjectDraftDialogProps) {
  const draft = useProjectDraft(resumeId)
  const [edited, setEdited] = useState<DraftFields | null>(null)
  const { mutate } = draft
  const values = edited ?? (draft.data ? fromDraft(draft.data) : null)
  const setValues = setEdited

  // Mounted per proof (keyed by the parent), so this runs once per opened card.
  useEffect(() => {
    if (proofId) mutate({ proofId, regenerate: false })
  }, [proofId, mutate])

  const placeholders = values ? findPlaceholders(`${values.description}\n${values.bullets}`) : []

  return (
    <Dialog open={proofId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add this project to your resume</DialogTitle>
          <DialogDescription>Drafted from your verified repo. Edit anything before adding it.</DialogDescription>
        </DialogHeader>
        {draft.isPending && (
          <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground" aria-live="polite">
            <Loader2 className="size-4 animate-spin" /> Drafting the entry…
          </p>
        )}
        {draft.isError && <FormError message={apiErrorMessage(draft.error, {}, { useServerDetail: true })} />}
        {values && !draft.isPending && (
          <div className="flex flex-col gap-3">
            <Field label="Project name" id="draft-name">
              <Input id="draft-name" value={values.name} onChange={(e) => setValues({ ...values, name: e.target.value })} />
            </Field>
            <Field label="Description" id="draft-description">
              <Textarea id="draft-description" rows={2} value={values.description} onChange={(e) => setValues({ ...values, description: e.target.value })} />
            </Field>
            <Field label="Bullets (one per line)" id="draft-bullets">
              <Textarea id="draft-bullets" rows={4} value={values.bullets} onChange={(e) => setValues({ ...values, bullets: e.target.value })} />
            </Field>
            <Field label="Tools and skills (comma separated)" id="draft-tools">
              <Input id="draft-tools" value={values.tools} onChange={(e) => setValues({ ...values, tools: e.target.value })} />
            </Field>
            <Field label="Link" id="draft-link">
              <Input id="draft-link" value={values.link} onChange={(e) => setValues({ ...values, link: e.target.value })} />
            </Field>
            <PlaceholderNote placeholders={placeholders} />
          </div>
        )}
        <DialogFooter className="gap-2 sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            disabled={!proofId || draft.isPending}
            onClick={() => {
              if (!proofId) return
              setEdited(null)
              mutate({ proofId, regenerate: true })
            }}
          >
            <RefreshCw /> Redraft
          </Button>
          <Button
            type="button"
            disabled={!values || !values.name.trim()}
            onClick={() => {
              if (!values) return
              onAccept({
                name: values.name.trim(),
                description: values.description.trim(),
                bullets: values.bullets.split('\n').map((b) => b.trim()).filter(Boolean),
                tools_and_skills: values.tools.split(',').map((t) => t.trim()).filter(Boolean),
                link: values.link.trim(),
              })
            }}
          >
            Add to resume
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

type DraftFields = { name: string; description: string; bullets: string; tools: string; link: string }

function fromDraft(d: ProjectDraft): DraftFields {
  return { name: d.name, description: d.description, bullets: d.bullets.join('\n'), tools: d.tools_and_skills.join(', '), link: d.link }
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}
