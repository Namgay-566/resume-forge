import { useEffect } from 'react'

const APP = 'ResumeForge'

export function formatTitle(title: string | null | undefined): string {
  return title && title !== APP ? `${title} · ${APP}` : APP
}

/** Set the tab title for a page. A page's own title (useEffect) lands after the app shell's
 * route-level default (useLayoutEffect), so specific titles like a resume's name win. */
export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    if (title !== undefined && title !== null) document.title = formatTitle(title)
  }, [title])
}
