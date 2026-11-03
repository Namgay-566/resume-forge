import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

import type { ExperienceLevel } from './types'

const EXPERIENCE_LEVELS: { value: ExperienceLevel; label: string; hint: string }[] = [
  { value: 'student', label: 'Student or fresher', hint: 'Studying or just graduated' },
  { value: 'entry', label: 'Entry level', hint: 'First year or two of work' },
  { value: 'mid', label: 'Mid level', hint: 'Several years of experience' },
  { value: 'senior', label: 'Senior', hint: 'Many years, often leading others' },
  { value: 'career_changer', label: 'Career changer', hint: 'Moving in from another field' },
]

const NONE = 'none' // Radix Select can't use '' as a value

/** Where the person is in their career. Tunes the ATS score and the AI's advice. */
export function ExperienceLevelSelect({
  id,
  value,
  onChange,
}: {
  id?: string
  value: ExperienceLevel | null
  onChange: (value: ExperienceLevel | null) => void
}) {
  return (
    <Select value={value ?? NONE} onValueChange={(v) => onChange(v === NONE ? null : (v as ExperienceLevel))}>
      <SelectTrigger id={id} className="w-full">
        {/* Just the label in the trigger; the hint is only shown in the list. */}
        <SelectValue placeholder="Choose your career stage">
          {EXPERIENCE_LEVELS.find((level) => level.value === value)?.label ?? 'Not set'}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>
          <span className="text-muted-foreground">Not set</span>
        </SelectItem>
        {EXPERIENCE_LEVELS.map((level) => (
          <SelectItem key={level.value} value={level.value}>
            <span className="flex flex-col">
              <span>{level.label}</span>
              <span className="text-xs text-muted-foreground">{level.hint}</span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
