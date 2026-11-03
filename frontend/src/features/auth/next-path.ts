/** Where to go after signing in or up: `?next=` or router state, internal paths only.
 * Anything absolute or protocol-relative ("//evil.com", "https://…") is ignored, so the
 * parameter can't be used as an open redirect. */
export function safeNextPath(...candidates: (string | null | undefined)[]): string | null {
  for (const value of candidates) {
    if (value && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/\\')) return value
  }
  return null
}
