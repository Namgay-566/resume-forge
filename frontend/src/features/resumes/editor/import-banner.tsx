import { Sparkles, X } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'

import type { ImportedState } from '../types'

export function ImportBanner({ imported }: ImportedState) {
  const [open, setOpen] = useState(true)
  if (!open) return null
  const { fileName, matchedSkills, unmatchedSkills } = imported

  return (
    <div role="status" className="flex gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm">
      <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="font-medium">Imported from {fileName}. Please review every section.</p>
        <p className="text-muted-foreground">
          Automatic import can miss or misplace details, especially dates and multi-column layouts.
          {matchedSkills.length > 0 &&
            ` We added ${matchedSkills.length} skill${matchedSkills.length === 1 ? '' : 's'} to your profile as unverified: ${matchedSkills.join(', ')}.`}
          {unmatchedSkills.length > 0 &&
            ` Not in our skills catalog yet: ${unmatchedSkills.join(', ')}.`}
        </p>
      </div>
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(false)} aria-label="Dismiss">
        <X />
      </Button>
    </div>
  )
}
