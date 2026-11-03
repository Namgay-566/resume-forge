import { Copy, FileText, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatRelativeTime } from '@/lib/format'

import type { ResumeSummary } from './types'

interface ResumeCardProps {
  resume: ResumeSummary
  onDuplicate: (id: string) => void
  onDelete: (id: string) => Promise<void>
  busy: boolean
}

export function ResumeCard({ resume, onDuplicate, onDelete, busy }: ResumeCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const editUrl = `/resumes/${resume.id}`

  return (
    <li className="relative flex flex-col gap-4 rounded-2xl border bg-card p-5 shadow-xs transition-[box-shadow,border-color] focus-within:ring-3 focus-within:ring-ring/40 hover:border-foreground/15 hover:shadow-md">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
          <FileText className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-heading text-base font-semibold tracking-tight">
            {/* The whole card is clickable via this link's ::after overlay. */}
            <Link to={editUrl} className="outline-none after:absolute after:inset-0">
              {resume.title}
            </Link>
          </h2>
          <p className="truncate text-sm text-muted-foreground">
            {resume.target_role?.name ?? 'No target role'}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="relative z-10" aria-label={`Actions for ${resume.title}`}>
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to={editUrl}>
                <Pencil />
                Open
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem disabled={busy} onSelect={() => onDuplicate(resume.id)}>
              <Copy />
              Duplicate
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" disabled={busy} onSelect={() => setConfirmOpen(true)}>
              <Trash2 />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary">{resume.type === 'cv' ? 'CV' : 'Resume'}</Badge>
        {resume.ats_score !== null && <Badge variant={resume.ats_score >= 80 ? 'success' : resume.ats_score >= 60 ? 'warning' : 'danger'}>ATS {resume.ats_score}</Badge>}
        <span className="ml-auto">Edited {formatRelativeTime(resume.updated_at)}</span>
      </div>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{resume.title}”?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the resume and its ATS history. This can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={async (event) => {
                event.preventDefault()
                await onDelete(resume.id)
                setConfirmOpen(false)
              }}
              disabled={busy}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  )
}
