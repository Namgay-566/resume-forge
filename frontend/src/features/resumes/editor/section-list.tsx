import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ArrowDown, ArrowUp, GripVertical, MoreHorizontal, PencilLine, Plus, Sparkles, Trash2 } from 'lucide-react'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { flushSync } from 'react-dom'
import { useFieldArray, useFormContext, useWatch } from 'react-hook-form'

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
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

import { emptyItem, LIMITS, type ResumeFormValues } from '../form-schema'
import { useSectionCatalog, useSectionSuggestions, type SectionCatalog } from '../sections/api'
import { isCoreKind, type CoreKind, type SectionKind } from '../types'
import { scrollToLocation } from './anchors'
import { GenericSection } from './generic-section'
import { SortableList, type SectionShell } from './section-card'
import { SECTION_ICONS } from './section-icons'
import {
  AchievementsSection,
  CertificationsSection,
  EducationSection,
  ExperienceSection,
  ProjectsSection,
  SkillsSection,
  SummarySection,
} from './sections'

type FormData = ResumeFormValues['data']

const CORE_COMPONENTS: Record<CoreKind, (props: { shell: SectionShell }) => React.ReactNode> = {
  summary: SummarySection,
  experience: ExperienceSection,
  education: EducationSection,
  skills: SkillsSection,
  projects: ProjectsSection,
  certifications: CertificationsSection,
  achievements: AchievementsSection,
}

/** Clearing a core section's content when it's removed (otherwise the server would put it
 * back: content is never silently hidden). */
const CLEAR_CORE: Record<CoreKind, Partial<FormData>> = {
  summary: { summary: '' },
  experience: { experience: [] },
  education: { education: [] },
  skills: { skills: [], show_verified_skills: false },
  projects: { projects: [] },
  certifications: { certifications: [] },
  achievements: { achievements: [] },
}

function coreHasContent(kind: CoreKind, data: FormData): boolean {
  if (kind === 'summary') return Boolean(data.summary.trim())
  return data[kind].length > 0
}

function headingOf(kind: SectionKind, title: string, catalog: SectionCatalog | undefined) {
  return title.trim() || catalog?.[kind]?.heading || kind.replace(/_/g, ' ')
}

const normalize = (text: string) => text.toLowerCase().split(/\s+/).filter(Boolean).join(' ')

/** The resume's sections in the user's order: drag (or use the menu) to reorder, rename,
 * remove, and add more, with suggestions for the target role and career stage. */
export function SectionList() {
  const { control } = useFormContext<ResumeFormValues>()
  // Sections have their own `id`, so the field array's key goes elsewhere.
  const { fields, move, remove, append } = useFieldArray({ control, name: 'data.sections', keyName: 'key' })
  const catalog = useSectionCatalog().data
  const [dragging, setDragging] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const titles = useWatch<ResumeFormValues>({ name: 'data.sections' }) as FormData['sections'] | undefined
  const labelOf = (i: number) => headingOf(fields[i]?.kind ?? 'custom', titles?.[i]?.title ?? '', catalog)

  /** Keyboard reordering from a section's handle: move one place, keep focus, announce it. */
  const moveBy = (from: number, to: number) => {
    if (to < 0 || to >= fields.length) return
    const key = fields[from].key
    const label = labelOf(from)
    // Reordering moves the focused DOM node, which drops focus. Render synchronously and
    // put it straight back, so a quick second key press still lands on the handle.
    flushSync(() => move(from, to))
    document.querySelector<HTMLElement>(`[data-section-handle="${key}"]`)?.focus()
    setAnnouncement(`${label} moved to position ${to + 1} of ${fields.length}.`)
  }

  return (
    <>
      <SortableList
        ids={fields.map((f) => f.key)}
        labelOf={labelOf}
        onMove={move}
        className="gap-4"
        uneven
        onDraggingChange={setDragging}
        overlay={(i) => <SectionDragPreview kind={fields[i].kind} heading={labelOf(i)} />}
      >
        {fields.map((field, index) => (
          <SortableSection
            key={field.key}
            sortId={field.key}
            index={index}
            total={fields.length}
            sectionId={field.id}
            kind={field.kind}
            catalog={catalog}
            collapsed={dragging}
            onMove={moveBy}
            onRemove={remove}
          />
        ))}
      </SortableList>
      <p className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>
      <p id="section-handle-hint" className="sr-only">
        Drag to reorder, or press the up and down arrow keys.
      </p>
      <AddSection
        present={fields.map((f) => f.kind)}
        full={fields.length >= LIMITS.sections}
        catalog={catalog}
        onAdd={(kind, title) => {
          const section = emptyItem.section(kind, title)
          append(section)
          window.setTimeout(() => scrollToLocation({ section: section.id, item_index: null }), 50)
        }}
      />
    </>
  )
}

/** What follows the pointer while a section is dragged: just its header. */
function SectionDragPreview({ kind, heading }: { kind: SectionKind; heading: string }) {
  const Icon = SECTION_ICONS[kind]
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-primary/40 bg-card px-3 py-3 shadow-lg ring-3 ring-primary/15">
      <GripVertical className="size-4 text-muted-foreground" aria-hidden />
      <span className="flex size-9 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
        <Icon className="size-[18px]" aria-hidden />
      </span>
      <span className="font-heading text-base font-semibold tracking-tight">{heading}</span>
    </div>
  )
}

interface SortableSectionProps {
  sortId: string
  index: number
  total: number
  sectionId: string
  kind: SectionKind
  catalog: SectionCatalog | undefined
  collapsed: boolean
  onMove: (from: number, to: number) => void
  onRemove: (index: number) => void
}

function SortableSection({ sortId, index, total, sectionId, kind, catalog, collapsed, onMove, onRemove }: SortableSectionProps) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: sortId })
  const { getValues, setValue } = useFormContext<ResumeFormValues>()
  const title = (useWatch<ResumeFormValues>({ name: `data.sections.${index}.title` }) as string | undefined) ?? ''
  const [renaming, setRenaming] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const heading = headingOf(kind, title, catalog)

  const removeNow = () => {
    if (isCoreKind(kind)) {
      for (const [field, value] of Object.entries(CLEAR_CORE[kind])) {
        setValue(`data.${field}` as 'data.summary', value as never, { shouldDirty: true })
      }
    }
    onRemove(index)
  }
  const askRemove = () => {
    const data = getValues('data')
    const filled = isCoreKind(kind)
      ? coreHasContent(kind, data)
      : (data.sections[index]?.entries.length ?? 0) > 0
    if (filled) setConfirming(true)
    else removeNow()
  }

  const shell: SectionShell = {
    id: sectionId,
    title: heading,
    containerRef: setNodeRef,
    collapsed,
    style: { transform: CSS.Translate.toString(transform), transition },
    className: cn(isDragging && 'border-dashed border-primary/50 opacity-50'),
    leading: (
      <button
        type="button"
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        data-section-handle={sortId}
        aria-label={`Reorder section: ${heading}`}
        aria-roledescription="sortable"
        aria-describedby="section-handle-hint"
        onKeyDown={(event: KeyboardEvent) => {
          if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
            event.preventDefault()
            onMove(index, index + (event.key === 'ArrowUp' ? -1 : 1))
          }
        }}
        className={cn(
          'flex size-8 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-muted-foreground transition-colors outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/40',
          isDragging && 'cursor-grabbing',
        )}
      >
        <GripVertical className="size-4" aria-hidden />
      </button>
    ),
    trailing: (
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Section options: ${heading}`} className="text-muted-foreground">
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem onSelect={() => setRenaming(true)}>
            <PencilLine /> Rename
          </DropdownMenuItem>
          <DropdownMenuItem disabled={index === 0} onSelect={() => onMove(index, index - 1)}>
            <ArrowUp /> Move up
          </DropdownMenuItem>
          <DropdownMenuItem disabled={index === total - 1} onSelect={() => onMove(index, index + 1)}>
            <ArrowDown /> Move down
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={askRemove}>
            <Trash2 /> Remove section
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
  }

  const spec = catalog?.[kind]
  const Core = isCoreKind(kind) ? CORE_COMPONENTS[kind] : null
  return (
    <>
      {Core ? <Core shell={shell} /> : spec ? <GenericSection shell={shell} index={index} spec={spec} /> : null}
      <RenameDialog
        open={renaming}
        onOpenChange={setRenaming}
        kind={kind}
        current={title}
        catalog={catalog}
        onSave={(next) => setValue(`data.sections.${index}.title`, next, { shouldDirty: true, shouldValidate: true })}
      />
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove “{heading}”?</AlertDialogTitle>
            <AlertDialogDescription>
              Everything in this section will be deleted from this resume. You can add the section back later, but not its content.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={removeNow}>
              Remove section
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

interface RenameDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kind: SectionKind
  current: string
  catalog: SectionCatalog | undefined
  onSave: (title: string) => void
}

/** Name a custom section, or rename any section. Warns when a heading isn't one ATS
 * systems recognise for that kind of section. */
function RenameDialog({ open, onOpenChange, kind, current, catalog, onSave }: RenameDialogProps) {
  const [value, setValue] = useState(current)
  const spec = catalog?.[kind]
  const standard = spec?.heading ?? ''
  const custom = kind === 'custom'
  const recognised =
    custom || !value.trim() || [standard, ...(spec?.standard_headings ?? [])].some((h) => normalize(h) === normalize(value))
  const submit = (event: FormEvent) => {
    event.preventDefault()
    event.stopPropagation() // this form sits inside the editor's form
    if (custom && !value.trim()) return
    onSave(value.trim())
    onOpenChange(false)
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setValue(current)
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{custom ? 'Name this section' : 'Rename section'}</DialogTitle>
            <DialogDescription>
              {custom ? 'This heading appears on your resume.' : `Leave it empty to use the standard heading, “${standard}”.`}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="section-title">Heading</Label>
            <Input
              id="section-title"
              value={value}
              maxLength={200}
              placeholder={standard}
              onChange={(event) => setValue(event.target.value)}
              aria-describedby="section-title-hint"
              autoFocus
            />
            <p id="section-title-hint" className={cn('text-xs', recognised ? 'text-muted-foreground' : 'text-warning-text')}>
              {recognised
                ? 'Standard headings help ATS systems find each part of your resume.'
                : `ATS systems may not recognise “${value.trim()}”. Headings like “${standard}” are safest.`}
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={custom && !value.trim()}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

interface AddSectionProps {
  present: SectionKind[]
  full: boolean
  catalog: SectionCatalog | undefined
  onAdd: (kind: SectionKind, title?: string) => void
}

/** "Add section": first what's suggested for the target role and career stage, then the rest,
 * then a section the user names. */
function AddSection({ present, full, catalog, onAdd }: AddSectionProps) {
  const [roleId, level, type] = useWatch<ResumeFormValues>({ name: ['target_role_id', 'experience_level', 'type'] }) as [
    string | null,
    ResumeFormValues['experience_level'],
    ResumeFormValues['type'],
  ]
  const suggestions = useSectionSuggestions(roleId, level, type).data
  const [naming, setNaming] = useState(false)
  const has = new Set(present)
  const required = new Set(suggestions?.required ?? [])
  const suggested = (suggestions?.sections ?? []).filter((k) => !has.has(k))
  const others = Object.values(catalog ?? {})
    .map((spec) => spec!.kind)
    .filter((k) => k !== 'custom' && !has.has(k) && !suggested.includes(k))
    .sort((a, b) => headingOf(a, '', catalog).localeCompare(headingOf(b, '', catalog)))
  const forWhom = suggestions?.role_name ? `Suggested for ${suggestions.role_name}` : 'Suggested for you'

  const item = (kind: SectionKind) => {
    const Icon = SECTION_ICONS[kind]
    return (
      <DropdownMenuItem key={kind} onSelect={() => onAdd(kind)}>
        <Icon />
        <span className="flex-1">{headingOf(kind, '', catalog)}</span>
        {required.has(kind) && <span className="text-[11px] font-medium text-warning-text">Required</span>}
      </DropdownMenuItem>
    )
  }

  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed px-4 py-5 text-center">
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="outline" disabled={full || !catalog}>
            <Plus /> Add section
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="center" className="max-h-[min(28rem,var(--radix-dropdown-menu-content-available-height))] w-64 overflow-y-auto">
          {suggested.length > 0 && (
            <>
              <DropdownMenuLabel className="flex items-center gap-1.5">
                <Sparkles className="size-3.5 text-highlight-text" aria-hidden /> {forWhom}
              </DropdownMenuLabel>
              {suggested.map(item)}
              <DropdownMenuSeparator />
            </>
          )}
          {others.length > 0 && (
            <>
              <DropdownMenuLabel>More sections</DropdownMenuLabel>
              {others.map(item)}
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuItem onSelect={() => setNaming(true)}>
            <PencilLine /> Custom section…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <p className="text-xs text-muted-foreground">
        {full
          ? `That's the maximum (${LIMITS.sections} sections).`
          : 'Licences, placements, publications, volunteering, languages, or a section you name yourself.'}
      </p>
      <RenameDialog open={naming} onOpenChange={setNaming} kind="custom" current="" catalog={catalog} onSave={(title) => onAdd('custom', title)} />
    </div>
  )
}
