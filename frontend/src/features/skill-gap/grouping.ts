import type { Importance, RoleSkillGap } from './types'

export type GroupBy = 'category' | 'importance'

export interface SkillSection {
  key: string
  title: string
  blurb: string
  skills: RoleSkillGap[]
}

export const IMPORTANCE: { key: Importance; title: string; blurb: string }[] = [
  { key: 'critical', title: 'Critical', blurb: 'Screened for first. Missing one of these usually means a rejection.' },
  { key: 'important', title: 'Important', blurb: 'Expected for most openings at this level.' },
  { key: 'nice_to_have', title: 'Nice to have', blurb: 'Help you stand out once the basics are covered.' },
]

export const IMPORTANCE_LABEL: Record<Importance, string> = {
  critical: 'Critical',
  important: 'Important',
  nice_to_have: 'Nice to have',
}

const RANK: Record<Importance, number> = { critical: 0, important: 1, nice_to_have: 2 }

function categoryBlurb(skills: RoleSkillGap[]): string {
  const critical = skills.filter((s) => s.importance === 'critical').length
  const count = `${skills.length} skill${skills.length === 1 ? '' : 's'}`
  return critical ? `${count} · ${critical} critical` : count
}

/**
 * Groups by the field's own skill categories ("Clinical skills", "CRM & sales tools"...).
 * Groups with the same name (every industry's "Credentials") are merged; groups keep the
 * order the seed data gives them, and skills inside a group run most important first.
 */
function byCategory(skills: RoleSkillGap[]): SkillSection[] {
  const groups = new Map<string, { order: number; skills: RoleSkillGap[] }>()
  for (const skill of skills) {
    const found = groups.get(skill.group.name)
    if (found) {
      found.skills.push(skill)
      found.order = Math.min(found.order, skill.group.sort_order)
    } else {
      groups.set(skill.group.name, { order: skill.group.sort_order, skills: [skill] })
    }
  }
  return [...groups.entries()]
    .sort(([nameA, a], [nameB, b]) => a.order - b.order || nameA.localeCompare(nameB))
    .map(([name, group]) => {
      const sorted = [...group.skills].sort((a, b) => RANK[a.importance] - RANK[b.importance])
      return { key: `cat-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, title: name, blurb: categoryBlurb(sorted), skills: sorted }
    })
}

function byImportance(skills: RoleSkillGap[]): SkillSection[] {
  return IMPORTANCE.map((level) => ({ ...level, skills: skills.filter((s) => s.importance === level.key) })).filter(
    (section) => section.skills.length > 0,
  )
}

export function groupSkills(skills: RoleSkillGap[], by: GroupBy): SkillSection[] {
  return by === 'category' ? byCategory(skills) : byImportance(skills)
}
