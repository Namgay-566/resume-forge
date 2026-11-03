import { Check, Copy, Search } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'

/** When nothing curated exists for a skill: say so, and offer a phrase to search for.
 * Never a link: we don't invent resources. */
export function NoCuratedResource({ phrase }: { phrase: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(phrase)
      } else {
        // Fallback for older browsers or non-HTTPS contexts
        const textArea = document.createElement("textarea")
        textArea.value = phrase
        textArea.style.position = "absolute"
        textArea.style.left = "-999999px"
        document.body.prepend(textArea)
        textArea.select()
        try {
          document.execCommand('copy')
        } catch (error) {
          console.error(error)
        } finally {
          textArea.remove()
        }
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard blocked: the phrase is still visible to copy by hand */
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-dashed p-3 text-sm">
      <p className="font-medium">No curated resource yet</p>
      <p className="text-muted-foreground">We only recommend resources we&apos;ve checked. Until we add one, try searching for:</p>
      <div className="flex flex-wrap items-center gap-2">
        <code className="flex items-center gap-1.5 rounded-md bg-muted px-2 py-1 font-sans">
          <Search className="size-3.5 text-muted-foreground" aria-hidden />
          {phrase}
        </code>
        <Button type="button" variant="ghost" size="sm" onClick={() => void copy()} aria-label={`Copy search phrase: ${phrase}`}>
          {copied ? <Check /> : <Copy />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <span className="sr-only" aria-live="polite">{copied ? 'Copied to clipboard' : ''}</span>
    </div>
  )
}