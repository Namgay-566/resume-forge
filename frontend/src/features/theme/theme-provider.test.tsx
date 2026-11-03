import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'

import { THEME_STORAGE_KEY } from './theme'
import { ThemeProvider } from './theme-provider'
import { ThemeToggle } from './theme-toggle'

afterEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
})

describe('theme', () => {
  it('starts from the remembered choice', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)

    expect(document.documentElement).toHaveClass('dark')
    expect(screen.getByRole('button', { name: /Theme: dark/ })).toBeInTheDocument()
  })

  it('remembers what the user picks, and forgets it for System', async () => {
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>)
    expect(document.documentElement).not.toHaveClass('dark') // system = light here

    await userEvent.click(screen.getByRole('button', { name: /Change theme/ }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /Dark/ }))
    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')

    await userEvent.click(screen.getByRole('button', { name: /Change theme/ }))
    await act(async () => userEvent.click(await screen.findByRole('menuitem', { name: /System/ })))
    expect(document.documentElement).not.toHaveClass('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })
})
