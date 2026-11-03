import { ArrowRight, Clock, ExternalLink } from 'lucide-react'
import { Link } from 'react-router'

import { NoCuratedResource } from '@/components/no-resource'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

import { useLearningResources } from './api'
import type { RoleSkillGap } from './types'

const TYPE_LABEL = { course: 'Course', docs: 'Docs', tutorial: 'Tutorial', video: 'Video' } as const

export function LearnSheet({
  skill,
  resumeId,
  onClose,
}: {
  skill: RoleSkillGap | null
  resumeId: string | null
  onClose: () => void
}) {
  const resources = useLearningResources(skill?.skill_id ?? null)

  return (
    <Sheet open={skill !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-lg">
        <SheetHeader className="border-b">
          <SheetTitle>Learn {skill?.name}</SheetTitle>
          <SheetDescription>
            Hand-picked, well-known resources. Once you can use it, upload proof to get the skill verified.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-3 p-4">
          {skill && resumeId && (
            <Button asChild size="sm" className="self-start">
              <Link to={`/roadmap?resume=${resumeId}#roadmap-${skill.slug}`}>
                Plan it in your roadmap: project idea and proof checklist <ArrowRight />
              </Link>
            </Button>
          )}
          {resources.isPending && <p className="text-sm text-muted-foreground">Loading resources…</p>}
          {resources.isError && <p className="text-sm text-danger-text">Couldn't load resources. Try again.</p>}
          {resources.data?.resources.length === 0 && <NoCuratedResource phrase={resources.data.search_phrase} />}
          <ul className="flex flex-col gap-2">
            {resources.data?.resources.map((r) => (
              <li key={r.id}>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex flex-col gap-1 rounded-lg border bg-background p-3 transition-colors hover:border-foreground/30 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <span className="flex items-start justify-between gap-2 text-sm font-medium">
                    {r.title}
                    <ExternalLink className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-label="opens in a new tab" />
                  </span>
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                    <span>{r.provider}</span>·<span>{TYPE_LABEL[r.type]}</span>·<span className="capitalize">{r.level}</span>
                    {r.est_hours && (
                      <span className="inline-flex items-center gap-1">
                        · <Clock className="size-3" aria-hidden /> ~{Number(r.est_hours)} h
                      </span>
                    )}
                    {r.is_free && <span className="rounded bg-success-muted px-1.5 text-success-text">Free</span>}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </SheetContent>
    </Sheet>
  )
}
