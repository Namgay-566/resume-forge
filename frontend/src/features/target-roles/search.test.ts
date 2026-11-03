import { describe, expect, it } from 'vitest'

import type { Industry, TargetRole } from './api'
import { groupRoles, hasExactTitle, matchesRole } from './search'

const industry = (slug: string, name: string): Industry => ({ id: slug, slug, name, description: '' })
const INDUSTRIES = [industry('technology', 'Technology'), industry('healthcare', 'Healthcare'), industry('skilled-trades', 'Skilled Trades')]

const role = (name: string, slug: string, ind: Industry): TargetRole => ({
  id: slug,
  name,
  slug,
  description: '',
  seniority: 'mid',
  source: 'curated',
  industry: { slug: ind.slug, name: ind.name, recommended_template: 'classic', profile_links: [] },
})
const [tech, health, trades] = INDUSTRIES
const ROLES = [
  role('Registered Nurse', 'rn', health),
  role('Healthcare Assistant', 'hca', health),
  role('Nursery Practitioner', 'np', health),
  role('Electrician', 'elec', trades),
  role('Frontend Developer', 'fe', tech),
]

describe('matchesRole', () => {
  it('matches word prefixes in any order, ignoring case and accents', () => {
    expect(matchesRole(ROLES[0], 'nur')).toBe(true)
    expect(matchesRole(ROLES[0], 'NURSE regis')).toBe(true)
    expect(matchesRole(ROLES[0], 'Régistered')).toBe(true)
    expect(matchesRole(ROLES[0], 'urse')).toBe(false) // not mid-word
  })

  it('matches the industry name too', () => {
    expect(matchesRole(ROLES[3], 'trades')).toBe(true)
  })
})

describe('groupRoles', () => {
  it('groups by industry in picker order', () => {
    const groups = groupRoles(ROLES, INDUSTRIES, '', null)

    expect(groups.map((g) => g.industry.slug)).toEqual(['technology', 'healthcare', 'skilled-trades'])
  })

  it('puts titles starting with the query first', () => {
    const [group] = groupRoles(ROLES, INDUSTRIES, 'nurs', null)

    expect(group.roles.map((r) => r.name)).toEqual(['Nursery Practitioner', 'Registered Nurse'])
  })

  it('filters by industry', () => {
    const groups = groupRoles(ROLES, INDUSTRIES, '', 'skilled-trades')

    expect(groups).toHaveLength(1)
    expect(groups[0].roles.map((r) => r.name)).toEqual(['Electrician'])
  })
})

it('knows when a typed title already exists', () => {
  expect(hasExactTitle(ROLES, '  electrician ')).toBe(true)
  expect(hasExactTitle(ROLES, 'Electric')).toBe(false)
})
