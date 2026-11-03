import { describe, expect, it } from 'vitest'

import { safeNextPath } from './next-path'

describe('safeNextPath', () => {
  it('accepts internal paths only', () => {
    expect(safeNextPath('/resumes?import=1')).toBe('/resumes?import=1')
    expect(safeNextPath('//evil.example/x', 'https://evil.example', '/\\evil.example')).toBeNull()
    expect(safeNextPath(null, undefined, '/dashboard')).toBe('/dashboard')
  })
})
