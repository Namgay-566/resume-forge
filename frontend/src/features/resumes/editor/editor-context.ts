import { createContext, useContext } from 'react'

import type { ProofLinks } from '@/features/suggestions/types'

export interface EditorContextValue {
  resumeId: string
  /** Flush autosave; resolves false if the draft has validation errors. */
  saveNow: () => Promise<boolean>
  /** Citation links for the user's proofs, keyed by proof id (for the preview and badges). */
  proofLinks: ProofLinks
}

export const EditorContext = createContext<EditorContextValue | null>(null)

export function useEditor(): EditorContextValue {
  const value = useContext(EditorContext)
  if (!value) throw new Error('useEditor must be used inside the resume editor')
  return value
}
