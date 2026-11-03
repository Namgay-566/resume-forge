// What the /design-system page documents. Values live in src/index.css; this is the index.

export const SCALE_STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const

export interface SemanticToken {
  name: string
  /** CSS variable holding the color. */
  variable: string
  /** What goes on it (shown as sample text). */
  on?: string
  use: string
}

export const SURFACES: SemanticToken[] = [
  { name: 'background', variable: '--background', on: '--foreground', use: 'Page' },
  { name: 'card', variable: '--card', on: '--card-foreground', use: 'Cards, inputs' },
  { name: 'popover', variable: '--popover', on: '--popover-foreground', use: 'Menus, dialogs, toasts' },
  { name: 'muted', variable: '--muted', on: '--muted-foreground', use: 'Recessed areas, secondary text' },
  { name: 'secondary', variable: '--secondary', on: '--secondary-foreground', use: 'Soft brand fills' },
  { name: 'primary', variable: '--primary', on: '--primary-foreground', use: 'Main actions, links, focus' },
  { name: 'highlight', variable: '--highlight', on: '--highlight-foreground', use: 'Encouragement, celebrations' },
]

export interface StatusToken {
  key: 'success' | 'warning' | 'danger'
  label: string
  meaning: string
}

export const STATUSES: StatusToken[] = [
  { key: 'success', label: 'Success', meaning: 'Verified skill: backed by a checked proof' },
  { key: 'warning', label: 'Warning', meaning: 'Unverified: on the resume, not yet proven' },
  { key: 'danger', label: 'Danger', meaning: 'Missing critical skill for the target role' },
]

export const TYPE_SCALE = [
  { token: 'text-display', size: '48 / 1.05', sample: 'Land the job you want' },
  { token: 'text-h1', size: '36 / 1.1', sample: 'Your resume, verified' },
  { token: 'text-h2', size: '28 / 1.2', sample: 'Skill gap for Registered Nurse' },
  { token: 'text-h3', size: '22 / 1.3', sample: 'IFRS reporting is your biggest gap' },
  { token: 'text-h4', size: '18 / 1.4', sample: 'Recent proof results' },
  { token: 'text-base', size: '16 / 1.6', sample: 'Body copy for longer explanations and resume content.' },
  { token: 'text-sm', size: '14 / 1.5', sample: 'Default UI text: labels, table cells, descriptions.' },
  { token: 'text-xs', size: '12 / 1.4', sample: 'Metadata, timestamps, helper text.' },
] as const

export const SPACING = [1, 2, 3, 4, 5, 6, 8, 10, 12, 16] as const

export const RADII = [
  { token: 'rounded-sm', px: 6, use: 'Tags inside inputs' },
  { token: 'rounded-md', px: 8, use: 'Small buttons, menu items' },
  { token: 'rounded-lg', px: 10, use: 'Buttons, inputs' },
  { token: 'rounded-xl', px: 14, use: 'Cards, toasts' },
  { token: 'rounded-2xl', px: 18, use: 'Dialogs' },
  { token: 'rounded-full', px: 999, use: 'Badges, avatars' },
] as const

export const SHADOWS = [
  { token: 'shadow-xs', use: 'Buttons, inputs, default cards' },
  { token: 'shadow-sm', use: 'Active tab, hovered card' },
  { token: 'shadow-md', use: 'Elevated cards' },
  { token: 'shadow-lg', use: 'Menus, popovers, toasts' },
  { token: 'shadow-xl', use: 'Dialogs' },
] as const
