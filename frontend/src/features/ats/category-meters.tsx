import { Delta } from './score-delta'
import type { CategoryScore } from './types'

const EMPTY_REASON: Record<string, string> = {
  keywords: 'Not scored: add a job description or choose a target role.',
}

/** One meter per category on the same 0-100 scale: one neutral hue, value as text. */
export function CategoryMeters({ categories, previous }: { categories: CategoryScore[]; previous?: CategoryScore[] }) {
  return (
    <ul className="flex flex-col gap-3">
      {categories.map((category) => {
        const before = previous?.find((p) => p.key === category.key)?.score
        return (
        <li key={category.key} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-2 text-sm">
            <span>
              <span className="font-medium">{category.label}</span>
              {category.score !== null && (
                <span className="ml-1.5 text-xs text-muted-foreground">
                  {Math.round(category.weight * 100)}% of score
                </span>
              )}
            </span>
            <span className="whitespace-nowrap text-muted-foreground">
              {category.score === null ? (
                'Not scored'
              ) : (
                <>
                  <span className="font-medium text-foreground">{category.score}</span> / 100
                  {typeof before === 'number' && before !== category.score && (
                    <span className="ml-1.5"><Delta value={category.score - before} /></span>
                  )}
                </>
              )}
            </span>
          </div>
          {category.score === null ? (
            <>
              <div className="h-2 rounded-[4px] border border-dashed" />
              <p className="text-xs text-muted-foreground">{EMPTY_REASON[category.key]}</p>
            </>
          ) : (
            <div
              className="h-2 overflow-hidden rounded-[4px] bg-primary/15"
              role="meter"
              aria-label={`${category.label} score`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={category.score}
            >
              <div
                className="h-full rounded-[4px] bg-primary transition-[width] duration-700"
                style={{ width: `${category.score}%` }}
              />
            </div>
          )}
        </li>
        )
      })}
    </ul>
  )
}
