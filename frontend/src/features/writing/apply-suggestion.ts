import type { UseFormReturn } from 'react-hook-form'

import type { ResumeFormValues } from '@/features/resumes/form-schema'

import type { Suggestion } from './types'

export type ApplyResult = { ok: true; undo: () => void } | { ok: false; reason: string }

const CHANGED = 'That part of your resume changed since this suggestion was made.'
const opts = { shouldDirty: true, shouldValidate: true, shouldTouch: true } as const
const same = (a: string | null | undefined, b: string | null | undefined) =>
  (a ?? '').trim().replace(/\s+/g, ' ') === (b ?? '').trim().replace(/\s+/g, ' ')

type Form = UseFormReturn<ResumeFormValues>
type Bullets = { value: string }[]

/**
 * Apply one accepted suggestion to the form (autosave then persists it).
 * Targets are found by their current content, not position, so earlier edits or moves don't
 * make a suggestion land on the wrong bullet. If the content no longer matches, nothing changes.
 */
export function applySuggestion(form: Form, s: Suggestion): ApplyResult {
  const { getValues, setValue } = form
  const { section, item_index: item } = s.location

  // Each undo reverses only its own change (found by content again), so undoing one
  // suggestion never discards other accepted suggestions or the user's own edits.
  switch (s.kind) {
    case 'rewrite_bullet':
    case 'move_bullet_up': {
      if ((section !== 'experience' && section !== 'projects') || item === null) {
        return { ok: false, reason: CHANGED }
      }
      const path = `data.${section}.${item}.bullets` as 'data.experience.0.bullets'
      const current = () => (getValues(path) as Bullets | undefined) ?? []
      const bullets = current()

      if (s.kind === 'rewrite_bullet') {
        const index = bullets.findIndex((b) => same(b.value, s.before))
        if (index === -1) return { ok: false, reason: CHANGED }
        const at = (i: number) => `${path}.${i}.value` as 'data.experience.0.bullets.0.value'
        setValue(at(index), s.after ?? '', opts)
        return {
          ok: true,
          undo: () => {
            const i = current().findIndex((b) => same(b.value, s.after))
            if (i !== -1) setValue(at(i), s.before ?? '', opts)
          },
        }
      }

      const target = s.after_items?.[0]
      const from = bullets.findIndex((b) => same(b.value, target))
      if (from === -1) return { ok: false, reason: CHANGED }
      setValue(path, [bullets[from], ...bullets.filter((_, i) => i !== from)], opts)
      return {
        ok: true,
        undo: () => {
          const now = current()
          const i = now.findIndex((b) => same(b.value, target))
          if (i === -1) return
          const rest = now.filter((_, j) => j !== i)
          rest.splice(Math.min(from, rest.length), 0, now[i])
          setValue(path, rest, opts)
        },
      }
    }

    case 'rewrite_summary': {
      const previous = getValues('data.summary')
      if (!same(previous, s.before)) return { ok: false, reason: CHANGED }
      setValue('data.summary', s.after ?? '', opts)
      return {
        ok: true,
        undo: () => {
          if (same(getValues('data.summary'), s.after)) setValue('data.summary', previous, opts)
        },
      }
    }

    case 'feature_skills': {
      const skills = getValues('data.skills')
      const previousOrder = skills.map((x) => x.name.toLowerCase())
      const rank = new Map((s.after_items ?? []).map((name, i) => [name.toLowerCase(), i]))
      if (!skills.some((x) => rank.has(x.name.toLowerCase()))) return { ok: false, reason: CHANGED }
      // Stable sort: suggested order first, everything else (including new skills) after.
      const byRank = (order: Map<string, number>) => (a: { name: string }, b: { name: string }) =>
        (order.get(a.name.toLowerCase()) ?? Infinity) - (order.get(b.name.toLowerCase()) ?? Infinity)
      setValue('data.skills', [...skills].sort(byRank(rank)), opts)
      return {
        ok: true,
        undo: () => {
          const original = new Map(previousOrder.map((name, i) => [name, i]))
          setValue('data.skills', [...getValues('data.skills')].sort(byRank(original)), opts)
        },
      }
    }

    case 'add_skill': {
      const skills = getValues('data.skills')
      const name = s.after ?? ''
      if (skills.some((x) => same(x.name.toLowerCase(), name.toLowerCase()))) {
        return { ok: true, undo: () => {} } // already there; nothing to undo
      }
      setValue('data.skills', [...skills, { name, skill_id: null, proof_id: null }], opts)
      return {
        ok: true,
        undo: () =>
          setValue(
            'data.skills',
            getValues('data.skills').filter((x) => !same(x.name.toLowerCase(), name.toLowerCase())),
            opts,
          ),
      }
    }
  }
}
