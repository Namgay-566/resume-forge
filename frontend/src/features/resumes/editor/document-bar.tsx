import { Controller, useFormContext, useWatch } from 'react-hook-form'

import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RolePicker } from '@/features/target-roles/role-picker'

import { ExperienceLevelSelect } from '../experience-level'
import type { ResumeFormValues } from '../form-schema'
import { sectionCompletion, trackedSections } from './completion'

/** Document type, target role, career stage, and how complete the resume is. */
export function DocumentBar() {
  const { control } = useFormContext<ResumeFormValues>()
  const data = useWatch({ control, name: 'data' })
  // Every section on the resume counts, except optional ones nobody has started.
  const tracked = trackedSections(data)
    .map((id) => sectionCompletion(id, data))
    .filter((c) => !(c.optional && c.state === 'empty'))
  const total = tracked.length
  const done = tracked.filter((c) => c.state === 'complete').length
  const percent = total ? Math.round((done / total) * 100) : 0

  return (
    <div className="flex flex-col gap-4 rounded-2xl border bg-card p-4 shadow-xs md:p-5">
      <div className="grid gap-3 sm:grid-cols-[8rem_1fr] lg:grid-cols-[8rem_1fr_12rem]">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="doc-type">Type</Label>
          <Controller
            control={control}
            name="type"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="doc-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="resume">Resume</SelectItem>
                  <SelectItem value="cv">CV</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="doc-role">Target role</Label>
          <Controller
            control={control}
            name="target_role_id"
            render={({ field }) => (
              <RolePicker id="doc-role" value={field.value} onChange={field.onChange} placeholder="Search for the job you want" />
            )}
          />
        </div>
        <div className="flex flex-col gap-1.5 sm:col-span-2 lg:col-span-1">
          <Label htmlFor="doc-level">Career stage</Label>
          <Controller
            control={control}
            name="experience_level"
            render={({ field }) => <ExperienceLevelSelect id="doc-level" value={field.value} onChange={field.onChange} />}
          />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-2 text-xs">
          <span className="font-medium">
            {done === total ? 'All sections complete' : `${done} of ${total} sections complete`}
          </span>
          <span className="text-muted-foreground tabular-nums">{percent}%</span>
        </div>
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="meter"
          aria-label="Sections complete"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={done}
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-success transition-[width] duration-500 ease-out-soft"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
    </div>
  )
}
