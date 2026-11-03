import { describe, expect, it } from 'vitest'

import { cn } from './utils'

describe('cn', () => {
  it('keeps a custom type-scale size alongside a text color', () => {
    expect(cn('text-h2 text-muted-foreground')).toBe('text-h2 text-muted-foreground')
    expect(cn('text-sm', 'text-h3')).toBe('text-h3') // sizes still override each other
    expect(cn('bg-primary', 'bg-success-muted')).toBe('bg-success-muted')
  })
})
