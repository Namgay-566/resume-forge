import { createContext } from 'react'

export type Theme = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'rf-theme' // also read by public/theme-init.js

export interface ThemeContextValue {
  /** What the user picked. */
  theme: Theme
  /** What's showing now ('system' resolved against the OS setting). */
  resolved: ResolvedTheme
  setTheme: (theme: Theme) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function readStoredTheme(): Theme {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system' // storage blocked (private mode, sandboxed iframe)
  }
}

export function systemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Switch without animating every transition on the page. */
export function applyTheme(resolved: ResolvedTheme): void {
  const root = document.documentElement
  root.classList.add('theme-switching')
  root.classList.toggle('dark', resolved === 'dark')
  // Two frames: styles recalculated with transitions off, then turned back on.
  requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove('theme-switching')))
}
