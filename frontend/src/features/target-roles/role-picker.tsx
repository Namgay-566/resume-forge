import { Check, ChevronDown, Loader2, Search, Sparkles } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'

import { apiErrorMessage } from '@/features/auth/api-error'
import { notifySuccess } from '@/lib/notify'
import { cn } from '@/lib/utils'

import { AiRoleNote } from './ai-role-note'
import { useCreateCustomRole, useIndustries, useTargetRoles, type TargetRole } from './api'
import { groupRoles, hasExactTitle } from './search'

interface RolePickerProps {
  id?: string
  value: string | null
  onChange: (roleId: string) => void
  invalid?: boolean
  placeholder?: string
  /** Render the list in the page flow, pushing content down, instead of floating over it.
   * Use inside scrolling containers such as dialogs, where a floating list gets clipped. */
  inline?: boolean
  className?: string
}

type Option = { kind: 'role'; role: TargetRole } | { kind: 'create'; title: string }

/** Choose a target role from any field: type to search, browse by industry, or create a role
 * from a job title the library doesn't have (the AI drafts its required skills). */
export function RolePicker({ id, value, onChange, invalid, placeholder, inline = false, className }: RolePickerProps) {
  const roles = useTargetRoles()
  const industries = useIndustries()
  const create = useCreateCustomRole()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [industry, setIndustry] = useState<string | null>(null)
  const [active, setActive] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const baseId = useId()
  const listId = `${baseId}-list`

  const selected = roles.data?.find((role) => role.id === value) ?? null
  const groups = useMemo(
    () => groupRoles(roles.data ?? [], industries.data ?? [], query, industry),
    [roles.data, industries.data, query, industry],
  )
  const title = query.trim()
  const canCreate = title.length >= 2 && !hasExactTitle(roles.data ?? [], title)
  const options: Option[] = useMemo(
    () => [
      ...groups.flatMap((g) => g.roles.map((role): Option => ({ kind: 'role', role }))),
      ...(canCreate ? [{ kind: 'create', title } as const] : []),
    ],
    [groups, canCreate, title],
  )
  const optionId = (index: number) => `${baseId}-opt-${index}`

  // Keep the highlighted option in range and in view.
  useEffect(() => setActive(0), [query, industry])
  useEffect(() => {
    if (!open) return
    document.getElementById(optionId(active))?.scrollIntoView?.({ block: 'nearest' })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- optionId is stable per render
  }, [active, open])

  // Close when focus or a click lands outside the picker.
  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const openList = () => {
    if (create.isPending) return
    setOpen(true)
    setError(null)
  }

  const choose = (role: TargetRole) => {
    onChange(role.id)
    setOpen(false)
    setQuery('')
    setIndustry(null)
  }

  const createRole = async (jobTitle: string) => {
    setError(null)
    try {
      const result = await create.mutateAsync({ title: jobTitle, industry })
      choose(result.role)
      if (result.created) {
        notifySuccess(`Created “${result.role.name}”`, 'AI drafted its required skills. Check them on your Skill Gap page.')
      }
    } catch (err) {
      setError(
        apiErrorMessage(err, {
          429: "You've used your AI allowance for now. Pick a similar role from the list, or try again later.",
        }),
      )
    } finally {
      inputRef.current?.focus()
    }
  }

  const pick = (option: Option | undefined) => {
    if (!option) return
    if (option.kind === 'role') choose(option.role)
    else void createRole(option.title)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) return openList()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive((i) => (options.length ? (i + step + options.length) % options.length : 0))
    } else if (event.key === 'Enter') {
      if (!open) return
      event.preventDefault()
      pick(options[active])
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
      setQuery('')
    } else if (event.key === 'Home' && open) {
      setActive(0)
    } else if (event.key === 'End' && open) {
      setActive(Math.max(0, options.length - 1))
    }
  }

  let index = -1
  const busy = create.isPending

  return (
    <div
      ref={rootRef}
      className={cn('relative flex flex-col gap-1.5', className)}
      data-picker-open={open ? 'true' : undefined}
      onBlur={(event) => {
        if (!rootRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false)
      }}
    >
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && options[active] ? optionId(active) : undefined}
          aria-invalid={invalid ? true : undefined}
          aria-busy={busy || undefined}
          autoComplete="off"
          spellCheck={false}
          disabled={busy}
          value={open ? query : busy ? title : (selected?.name ?? '')}
          placeholder={
            open && selected
              ? selected.name
              : roles.isPending
                ? 'Loading roles…'
                : (placeholder ?? 'Search any job title')
          }
          onFocus={openList}
          onClick={openList}
          onChange={(event) => {
            setQuery(event.target.value)
            if (!open) setOpen(true)
          }}
          onKeyDown={onKeyDown}
          className={cn(
            'h-9 w-full min-w-0 rounded-lg border border-input bg-card py-1 pr-9 pl-9 text-base shadow-xs transition-[color,border-color,box-shadow] duration-150 outline-none placeholder:text-muted-foreground md:text-sm',
            'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/20 disabled:cursor-progress disabled:bg-muted',
            'aria-invalid:border-danger aria-invalid:ring-3 aria-invalid:ring-danger/15',
            !open && selected && 'font-medium placeholder:text-foreground',
          )}
        />
        {busy ? (
          <Loader2 className="absolute top-1/2 right-3 size-4 -translate-y-1/2 animate-spin text-muted-foreground" aria-hidden />
        ) : (
          <ChevronDown
            className={cn('pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground transition-transform', open && 'rotate-180')}
            aria-hidden
          />
        )}
      </div>

      {busy && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
          <Sparkles className="size-3.5 text-highlight-text" aria-hidden />
          Building a skill profile for “{title}”. This takes a few seconds…
        </p>
      )}
      {error && !busy && <p className="text-sm text-danger-text" role="alert">{error}</p>}
      {!open && !busy && selected && (
        <p className="text-xs text-muted-foreground">
          {selected.industry.name}
          {selected.seniority ? ` · ${seniorityLabel(selected.seniority)}` : ''}
        </p>
      )}
      {!open && !busy && selected?.source === 'ai_generated' && <AiRoleNote compact />}

      {open && (
        <div
          className={cn(
            'flex flex-col overflow-hidden rounded-xl border bg-popover text-popover-foreground',
            inline ? 'shadow-sm' : 'absolute inset-x-0 top-10 z-50 shadow-lg',
          )}
        >
          {industries.data && industries.data.length > 1 && (
            <div className="flex gap-1.5 overflow-x-auto border-b px-2 py-2 [contain:inline-size] [scrollbar-width:thin]" role="group" aria-label="Browse by industry">
              <IndustryChip label="All fields" pressed={industry === null} onClick={() => setIndustry(null)} />
              {industries.data.map((i) => (
                <IndustryChip
                  key={i.slug}
                  label={i.name}
                  pressed={industry === i.slug}
                  onClick={() => setIndustry(industry === i.slug ? null : i.slug)}
                />
              ))}
            </div>
          )}
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-label="Target roles"
            className={cn('overflow-y-auto overscroll-contain py-1', inline ? 'max-h-60' : 'max-h-72')}
          >
            {roles.isError && <li className="px-3 py-2 text-sm text-danger-text">Couldn't load roles.</li>}
            {groups.map((group) => (
              <li key={group.industry.slug} role="presentation">
                <p className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase" aria-hidden>
                  {group.industry.name}
                </p>
                <ul role="group" aria-label={group.industry.name}>
                  {group.roles.map((role) => {
                    index += 1
                    const i = index
                    const isSelected = role.id === value
                    return (
                      <li
                        key={role.id}
                        id={optionId(i)}
                        role="option"
                        aria-selected={isSelected}
                        onPointerDown={(event) => event.preventDefault()} // keep focus in the input
                        onClick={() => choose(role)}
                        onPointerMove={() => active !== i && setActive(i)}
                        className={cn(
                          'mx-1 flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                          i === active && 'bg-accent text-accent-foreground',
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">{role.name}</span>
                        {role.source === 'ai_generated' && (
                          <span className="flex shrink-0 items-center gap-1 text-[11px] text-info-text">
                            <Sparkles className="size-3" aria-hidden />
                            AI-generated
                          </span>
                        )}
                        {isSelected && <Check className="size-4 shrink-0 text-primary" aria-hidden />}
                      </li>
                    )
                  })}
                </ul>
              </li>
            ))}
            {groups.length === 0 && !roles.isPending && !canCreate && (
              <li className="px-3 py-2 text-sm text-muted-foreground">No roles match.</li>
            )}
            {canCreate ? (
              (() => {
                index += 1
                const i = index
                return (
                  <li
                    id={optionId(i)}
                    role="option"
                    aria-selected={false}
                    onPointerDown={(event) => event.preventDefault()}
                    onClick={() => void createRole(title)}
                    onPointerMove={() => active !== i && setActive(i)}
                    className={cn(
                      'mx-1 mt-1 flex cursor-pointer items-start gap-2 rounded-md border-t px-2 py-2 text-sm',
                      i === active && 'bg-accent text-accent-foreground',
                    )}
                  >
                    <Sparkles className="mt-0.5 size-4 shrink-0 text-highlight-text" aria-hidden />
                    <span className="flex flex-col">
                      <span>
                        Can't find your role? Use <span className="font-medium">“{title}”</span>
                      </span>
                      <span className="text-xs text-muted-foreground">AI builds its required skills. Only you will see it.</span>
                    </span>
                  </li>
                )
              })()
            ) : (
              !title && (
                <li role="presentation" className="mx-1 mt-1 flex items-center gap-2 border-t px-2 py-2 text-xs text-muted-foreground">
                  <Sparkles className="size-3.5 shrink-0 text-highlight-text" aria-hidden />
                  Can't find your role? Type the job title and we'll build it.
                </li>
              )
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

function IndustryChip({ label, pressed, onClick }: { label: string; pressed: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onPointerDown={(event) => event.preventDefault()} // keep typing focus in the search box
      onClick={onClick}
      className={cn(
        'shrink-0 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/30',
        pressed ? 'border-primary bg-primary text-primary-foreground' : 'bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground',
      )}
    >
      {label}
    </button>
  )
}

const SENIORITY: Record<string, string> = { junior: 'Junior', entry: 'Entry level', mid: 'Mid level', senior: 'Senior' }

function seniorityLabel(seniority: string): string {
  return SENIORITY[seniority] ?? seniority
}
