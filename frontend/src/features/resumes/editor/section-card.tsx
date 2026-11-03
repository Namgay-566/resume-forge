import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MeasuringStrategy,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from '@dnd-kit/core'
import { restrictToParentElement, restrictToVerticalAxis } from '@dnd-kit/modifiers'
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ArrowDown, ArrowUp, Check, ChevronDown, GripVertical, Plus, Trash2, type LucideIcon } from 'lucide-react'
import { Collapsible as CollapsiblePrimitive } from 'radix-ui'
import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { useWatch } from 'react-hook-form'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import type { ResumeFormValues } from '../form-schema'
import { OPEN_EVENT, sectionAnchor } from './anchors'
import { sectionCompletion, type SectionId } from './completion'

/** Opens when something (an ATS fix link) targets this element by id. */
function useOpenOnTarget(anchorId: string | undefined, setOpen: (open: boolean) => void) {
  useEffect(() => {
    if (!anchorId) return
    const onOpen = (event: Event) => {
      if ((event as CustomEvent<string[]>).detail.includes(anchorId)) setOpen(true)
    }
    window.addEventListener(OPEN_EVENT, onOpen)
    return () => window.removeEventListener(OPEN_EVENT, onOpen)
  }, [anchorId, setOpen])
}

// --- Sections -------------------------------------------------------------------------

/** What the section list passes each section: its id, heading and header controls. */
export interface SectionShell {
  id: SectionId
  title: string
  /** Header controls outside the collapse toggle (drag handle, section menu). */
  leading?: ReactNode
  trailing?: ReactNode
  /** For drag-and-drop reordering of whole sections. */
  containerRef?: (element: HTMLElement | null) => void
  style?: CSSProperties
  className?: string
  /** Show only the header (while sections are being reordered). */
  collapsed?: boolean
}

interface SectionCardProps extends SectionShell {
  icon: LucideIcon
  description?: string
  children: ReactNode
  onAdd?: () => void
  addLabel?: string
  /** With `count`, disables Add at the cap (mirrors the server's limits). */
  max?: number
  count?: number
}

export function SectionCard({
  id,
  title,
  icon: Icon,
  description,
  children,
  onAdd,
  addLabel,
  max,
  count = 0,
  leading,
  trailing,
  containerRef,
  style,
  className,
  collapsed = false,
}: SectionCardProps) {
  const [open, setOpen] = useState(true)
  useOpenOnTarget(sectionAnchor(id), setOpen)
  const full = max !== undefined && count >= max

  return (
    <CollapsiblePrimitive.Root asChild open={open && !collapsed} onOpenChange={setOpen}>
      <section
        ref={containerRef}
        style={style}
        id={sectionAnchor(id)}
        aria-labelledby={`${id}-heading`}
        className={cn('scroll-mt-32 rounded-2xl border bg-card shadow-xs transition-shadow data-[state=open]:shadow-sm', className)}
      >
        <div className={cn('flex items-center', (leading || trailing) && 'gap-0.5 pr-2', leading && 'pl-1.5')}>
        {leading}
        <h2 id={`${id}-heading`} className="m-0 min-w-0 flex-1">
          <CollapsiblePrimitive.Trigger
            className={cn(
              'group/section flex w-full items-center gap-3 rounded-2xl py-3.5 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/40',
              leading ? 'px-2' : 'px-4 md:px-5',
            )}
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-secondary-foreground">
              <Icon className="size-[18px]" aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-heading text-base font-semibold tracking-tight">{title}</span>
              <CompletionDetail id={id} />
            </span>
            <CompletionMark id={id} />
            <ChevronDown
              className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=closed]/section:-rotate-90"
              aria-hidden
            />
          </CollapsiblePrimitive.Trigger>
        </h2>
        {trailing}
        </div>
        <CollapsiblePrimitive.Content className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
          <div className="flex flex-col gap-4 border-t px-4 pt-4 pb-5 md:px-5">
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
            {children}
            {onAdd && (
              <div className="flex items-center gap-3">
                <Button type="button" variant="outline" size="sm" onClick={onAdd} disabled={full}>
                  <Plus />
                  {addLabel ?? 'Add'}
                </Button>
                {full && <p className="text-xs text-muted-foreground">That&apos;s the maximum ({max}).</p>}
              </div>
            )}
          </div>
        </CollapsiblePrimitive.Content>
      </section>
    </CollapsiblePrimitive.Root>
  )
}

function useCompletion(id: SectionId) {
  const data = useWatch<ResumeFormValues, 'data'>({ name: 'data' })
  return sectionCompletion(id, data)
}

function CompletionDetail({ id }: { id: SectionId }) {
  const { state, detail } = useCompletion(id)
  return <span className={cn('block truncate text-xs', state === 'complete' ? 'text-success-text' : 'text-muted-foreground')}>{detail}</span>
}

/** Checkmark when filled in; a ring while partial; a dashed ring when not started. */
function CompletionMark({ id }: { id: SectionId }) {
  const { state, optional } = useCompletion(id)
  if (state === 'complete') {
    return (
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-success text-success-foreground" aria-label="Complete">
        <Check className="size-3.5" strokeWidth={3} aria-hidden />
      </span>
    )
  }
  return (
    <span
      aria-label={state === 'partial' ? 'In progress' : optional ? 'Optional, not started' : 'Not started'}
      className={cn(
        'size-6 shrink-0 rounded-full border-2',
        state === 'partial' ? 'border-warning border-r-transparent' : 'border-dashed border-muted-foreground/40',
      )}
    />
  )
}

// --- Sortable items -----------------------------------------------------------------------

interface SortableListProps {
  ids: string[]
  /** Label of item `index`, for screen-reader announcements. */
  labelOf: (index: number) => string
  onMove: (from: number, to: number) => void
  children: ReactNode
  className?: string
  /** Items of very different heights (whole sections). They collapse to their headers while
   * one is dragged (see onDraggingChange), layout is re-measured throughout, and `overlay`
   * draws the dragged item under the pointer (the collapse moves the item itself away). */
  uneven?: boolean
  onDraggingChange?: (dragging: boolean) => void
  overlay?: (index: number) => ReactNode
}

/** Drag to reorder with mouse, touch or keyboard (Space to lift, arrows to move, Space to drop). */
export function SortableList({ ids, labelOf, onMove, children, className, uneven = false, onDraggingChange, overlay }: SortableListProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const pointer = useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  const keyboard = useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  // Uneven lists handle arrow keys themselves: dnd-kit's keyboard dragging measures a tall
  // item before it collapses and loses the first move.
  const sensors = useSensors(pointer, ...(uneven ? [] : [keyboard]))
  const name = (id: string | number) => labelOf(ids.indexOf(String(id)))
  const position = (id: string | number | undefined) => (id === undefined ? 0 : ids.indexOf(String(id)) + 1)
  const announcements: Announcements = {
    onDragStart: ({ active }) =>
      uneven ? `Picked up ${name(active.id)}.` : `Picked up ${name(active.id)}. Use the arrow keys to move it, Space to drop, Escape to cancel.`,
    onDragOver: ({ active, over }) => (over ? `${name(active.id)} is now at position ${position(over.id)} of ${ids.length}.` : undefined),
    onDragEnd: ({ active, over }) => (over ? `Dropped ${name(active.id)} at position ${position(over.id)} of ${ids.length}.` : `Dropped ${name(active.id)}.`),
    onDragCancel: ({ active }) => `Cancelled. ${name(active.id)} is back where it was.`,
  }
  const stop = () => {
    setActiveIndex(null)
    onDraggingChange?.(false)
  }
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    stop()
    if (!over || active.id === over.id) return
    onMove(ids.indexOf(String(active.id)), ids.indexOf(String(over.id)))
  }
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={uneven ? [restrictToVerticalAxis] : [restrictToVerticalAxis, restrictToParentElement]}
      measuring={uneven ? { droppable: { strategy: MeasuringStrategy.Always } } : undefined}
      onDragStart={({ active }) => {
        setActiveIndex(ids.indexOf(String(active.id)))
        onDraggingChange?.(true)
      }}
      onDragCancel={stop}
      onDragEnd={onDragEnd}
      accessibility={{ announcements }}
    >
      <SortableContext items={ids} strategy={verticalListSortingStrategy}>
        <div className={cn('flex flex-col gap-3', className)}>{children}</div>
      </SortableContext>
      {overlay && <DragOverlay modifiers={[restrictToVerticalAxis]}>{activeIndex !== null ? overlay(activeIndex) : null}</DragOverlay>}
    </DndContext>
  )
}

interface ItemCardProps {
  /** dnd-kit id: the field array's stable `field.id`. */
  sortId: string
  /** DOM id so the ATS fix list can jump here (see anchors.ts). */
  anchorId?: string
  heading: ReactNode
  /** Plain-text name for screen-reader labels on the controls. */
  label: string
  index: number
  onRemove: (index: number) => void
  children: ReactNode
}

/** One entry in a repeatable section: drag handle, collapsible body, remove. */
export function ItemCard({ sortId, anchorId, heading, label, index, onRemove, children }: ItemCardProps) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: sortId })
  const [open, setOpen] = useState(true)
  useOpenOnTarget(anchorId, setOpen)

  return (
    <CollapsiblePrimitive.Root open={open} onOpenChange={setOpen} asChild>
      <div
        ref={setNodeRef}
        id={anchorId}
        style={{ transform: CSS.Translate.toString(transform), transition }}
        className={cn(
          'relative scroll-mt-32 rounded-xl border bg-background transition-shadow',
          isDragging && 'z-10 border-primary/40 shadow-lg ring-3 ring-primary/15',
        )}
      >
        <div className="flex items-center gap-1 py-1.5 pr-1.5 pl-1">
          <button
            type="button"
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            aria-label={`Reorder ${label}`}
            aria-roledescription="sortable"
            className={cn(
              'flex size-8 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-muted-foreground transition-colors outline-none hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/40',
              isDragging && 'cursor-grabbing',
            )}
          >
            <GripVertical className="size-4" aria-hidden />
          </button>
          <CollapsiblePrimitive.Trigger className="group/item flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-1.5 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/40">
            <span className="min-w-0 flex-1 truncate text-sm font-semibold">{heading}</span>
            <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=closed]/item:-rotate-90" aria-hidden />
            <span className="sr-only">{open ? 'Collapse' : 'Expand'} {label}</span>
          </CollapsiblePrimitive.Trigger>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => onRemove(index)}
            aria-label={`Remove ${label}`}
            className="text-muted-foreground hover:bg-danger-muted hover:text-danger-text"
          >
            <Trash2 />
          </Button>
        </div>
        <CollapsiblePrimitive.Content className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
          <div className="flex flex-col gap-4 border-t px-4 pt-4 pb-4">{children}</div>
        </CollapsiblePrimitive.Content>
      </div>
    </CollapsiblePrimitive.Root>
  )
}

// --- Row controls (bullets, skills) --------------------------------------------------------

interface ItemControlsProps {
  index: number
  total: number
  label: string
  onMove: (from: number, to: number) => void
  onRemove: (index: number) => void
}

export function ItemControls({ index, total, label, onMove, onRemove }: ItemControlsProps) {
  return (
    <div className="flex shrink-0 items-center">
      <Button type="button" variant="ghost" size="icon-sm" disabled={index === 0} onClick={() => onMove(index, index - 1)} aria-label={`Move ${label} up`}>
        <ArrowUp />
      </Button>
      <Button type="button" variant="ghost" size="icon-sm" disabled={index === total - 1} onClick={() => onMove(index, index + 1)} aria-label={`Move ${label} down`}>
        <ArrowDown />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        onClick={() => onRemove(index)}
        aria-label={`Remove ${label}`}
        className="text-muted-foreground hover:bg-danger-muted hover:text-danger-text"
      >
        <Trash2 />
      </Button>
    </div>
  )
}
