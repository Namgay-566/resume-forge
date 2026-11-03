import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { PageSize, Spelling, User } from '@/features/auth/types'
import { ExperienceLevelSelect } from '@/features/resumes/experience-level'
import { TEMPLATES } from '@/features/resumes/preview/templates'
import type { ResumeTemplate, ResumeType } from '@/features/resumes/types'

import { useSavePreference } from './api'
import { SettingRow, SettingsSection } from './settings-section'

const RECOMMENDED = 'recommended' // Radix Select can't use '' or null as a value
const NO_PREFERENCE = 'none'

const PAGE_SIZES: { value: PageSize; label: string; hint: string }[] = [
  { value: 'a4', label: 'A4', hint: 'Most of the world' },
  { value: 'letter', label: 'US Letter', hint: 'United States and Canada' },
]

const SPELLINGS: { value: Spelling | typeof NO_PREFERENCE; label: string }[] = [
  { value: NO_PREFERENCE, label: 'Match my resume' },
  { value: 'en_gb', label: 'British English (organise, colour)' },
  { value: 'en_us', label: 'American English (organize, color)' },
]

export function ResumeDefaultsSection({ user }: { user: User }) {
  const prefs = user.preferences
  const save = useSavePreference()

  return (
    <SettingsSection
      id="resume-defaults"
      title="Resume defaults"
      description="What every new resume starts with. You can still change any of them for a single resume."
    >
      <SettingRow
        label="Document type"
        hint="A resume is 1–2 pages for one role. A CV is a full history, common in academia and many countries."
      >
        <RadioGroup
          value={prefs.default_resume_type}
          onValueChange={(value) => save({ default_resume_type: value as ResumeType })}
          className="flex gap-2"
          aria-label="Document type"
        >
          {(['resume', 'cv'] as const).map((value) => (
            <Label
              key={value}
              htmlFor={`default-type-${value}`}
              className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5"
            >
              <RadioGroupItem id={`default-type-${value}`} value={value} />
              {value === 'cv' ? 'CV' : 'Resume'}
            </Label>
          ))}
        </RadioGroup>
      </SettingRow>

      <SettingRow
        label="Career stage"
        htmlFor="default-level"
        hint="Tunes scoring and advice. Students and career changers are judged on studies, projects and transferable skills."
      >
        <div className="w-full @xl:w-64">
          <ExperienceLevelSelect
            id="default-level"
            value={prefs.default_experience_level}
            onChange={(value) => save({ default_experience_level: value })}
          />
        </div>
      </SettingRow>

      <SettingRow label="Template" htmlFor="default-template" hint="Every template is single-column and ATS-friendly.">
        <Select
          value={prefs.default_template ?? RECOMMENDED}
          onValueChange={(value) =>
            save({ default_template: value === RECOMMENDED ? null : (value as ResumeTemplate) })
          }
        >
          <SelectTrigger id="default-template" className="w-full @xl:w-64">
            <SelectValue>
              {TEMPLATES.find((t) => t.value === prefs.default_template)?.label ?? 'Recommended for my field'}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={RECOMMENDED}>
              <span className="flex flex-col">
                <span>Recommended for my field</span>
                <span className="text-xs text-muted-foreground">Picked from your target role</span>
              </span>
            </SelectItem>
            {TEMPLATES.map((template) => (
              <SelectItem key={template.value} value={template.value}>
                <span className="flex flex-col">
                  <span>{template.label}</span>
                  <span className="text-xs text-muted-foreground">{template.suits}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SettingRow>

      <SettingRow label="Page size" hint="Used for PDF and Word downloads and the editor preview.">
        <RadioGroup
          value={prefs.page_size}
          onValueChange={(value) => save({ page_size: value as PageSize })}
          className="flex gap-2"
          aria-label="Page size"
        >
          {PAGE_SIZES.map((size) => (
            <Label
              key={size.value}
              htmlFor={`page-size-${size.value}`}
              title={size.hint}
              className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5"
            >
              <RadioGroupItem id={`page-size-${size.value}`} value={size.value} />
              {size.label}
            </Label>
          ))}
        </RadioGroup>
      </SettingRow>

      <SettingRow label="Spelling" htmlFor="spelling" hint="The spelling AI writing help uses in rewrites and summaries.">
        <Select
          value={prefs.spelling ?? NO_PREFERENCE}
          onValueChange={(value) => save({ spelling: value === NO_PREFERENCE ? null : (value as Spelling) })}
        >
          <SelectTrigger id="spelling" className="w-full @xl:w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SPELLINGS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </SettingRow>
    </SettingsSection>
  )
}
