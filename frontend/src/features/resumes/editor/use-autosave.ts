import { useCallback, useEffect, useRef, useState } from 'react'
import type { UseFormReturn } from 'react-hook-form'

import { resumeFormSchema, toPayload, type ResumeFormValues } from '../form-schema'
import type { ResumeUpdate } from '../types'

export type SaveStatus = 'saved' | 'pending' | 'saving' | 'invalid' | 'error'

export const AUTOSAVE_DELAY_MS = 1500

/**
 * Debounced autosave. Saves run one at a time, identical payloads are skipped,
 * invalid drafts wait for the user to fix them, and pending edits are flushed on unmount.
 */
export function useAutosave(
  form: UseFormReturn<ResumeFormValues>,
  save: (payload: ResumeUpdate) => Promise<unknown>,
  delay = AUTOSAVE_DELAY_MS,
) {
  const [status, setStatus] = useState<SaveStatus>('saved')
  const [savedAt, setSavedAt] = useState<Date | null>(null)

  const saveRef = useRef(save)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const inFlight = useRef<Promise<boolean> | null>(null)
  const lastSaved = useRef(JSON.stringify(toPayload(form.getValues())))
  const statusRef = useRef(status)

  useEffect(() => {
    saveRef.current = save
  }, [save])
  useEffect(() => {
    statusRef.current = status
  }, [status])

  /** Save now. Resolves true once the server has the current values. */
  const flush = useCallback(async (): Promise<boolean> => {
    clearTimeout(timer.current)
    // Wait for the previous save so requests never overtake each other.
    while (inFlight.current) await inFlight.current

    const values = form.getValues()
    if (!resumeFormSchema.safeParse(values).success) {
      void form.trigger()
      setStatus('invalid')
      return false
    }
    const payload = toPayload(values)
    const json = JSON.stringify(payload)
    if (json === lastSaved.current) {
      setStatus('saved')
      return true
    }

    setStatus('saving')
    inFlight.current = saveRef
      .current(payload)
      .then(() => {
        lastSaved.current = json
        setSavedAt(new Date())
        const changedMeanwhile = JSON.stringify(toPayload(form.getValues())) !== json
        setStatus(changedMeanwhile ? 'pending' : 'saved')
        return true
      })
      .catch(() => {
        setStatus('error')
        return false
      })
      .finally(() => {
        inFlight.current = null
      })
    return inFlight.current
  }, [form])

  useEffect(() => {
    const subscription = form.watch(() => {
      setStatus('pending')
      clearTimeout(timer.current)
      timer.current = setTimeout(() => void flush(), delay)
    })
    return () => subscription.unsubscribe()
  }, [form, flush, delay])

  // Leaving the editor: save whatever is still waiting.
  useEffect(
    () => () => {
      if (statusRef.current === 'pending') void flush()
      clearTimeout(timer.current)
    },
    [flush],
  )

  // Closing the tab: ask the browser to warn while changes are unsaved.
  useEffect(() => {
    const unsaved = status === 'pending' || status === 'saving' || status === 'invalid' || status === 'error'
    if (!unsaved) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [status])

  return { status, savedAt, saveNow: flush }
}
