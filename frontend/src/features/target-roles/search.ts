import type { Industry, TargetRole } from './api'

export interface RoleGroup {
  industry: { slug: string; name: string }
  roles: TargetRole[]
}

const normalize = (text: string) =>
  text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9+#]+/g, ' ')
    .trim()

/** Whether every word typed starts a word in the role's title (or its industry's name),
 * so "reg nur" finds Registered Nurse and "health" lists every Healthcare role. */
export function matchesRole(role: TargetRole, query: string): boolean {
  const words = normalize(query).split(' ').filter(Boolean)
  if (words.length === 0) return true
  const haystack = normalize(`${role.name} ${role.industry.name}`).split(' ')
  return words.every((word) => haystack.some((w) => w.startsWith(word)))
}

/** Roles matching the query (and industry filter), grouped by industry in picker order.
 * Titles that start with the query come first within a group. */
export function groupRoles(
  roles: TargetRole[],
  industries: Industry[],
  query: string,
  industry: string | null,
): RoleGroup[] {
  const q = normalize(query)
  const order = new Map(industries.map((i, index) => [i.slug, index]))
  const groups = new Map<string, RoleGroup>()
  for (const role of roles) {
    if (industry && role.industry.slug !== industry) continue
    if (!matchesRole(role, query)) continue
    const group = groups.get(role.industry.slug) ?? { industry: role.industry, roles: [] }
    group.roles.push(role)
    groups.set(role.industry.slug, group)
  }
  const rank = (role: TargetRole) => (q && normalize(role.name).startsWith(q) ? 0 : 1)
  for (const group of groups.values()) {
    group.roles.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
  }
  return [...groups.values()].sort(
    (a, b) => (order.get(a.industry.slug) ?? 99) - (order.get(b.industry.slug) ?? 99),
  )
}

/** True when the query is exactly an existing title, so offering "create it" makes no sense. */
export function hasExactTitle(roles: TargetRole[], query: string): boolean {
  const q = normalize(query)
  return roles.some((role) => normalize(role.name) === q)
}
