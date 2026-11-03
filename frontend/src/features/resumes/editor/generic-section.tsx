import { useFieldArray, useFormContext, useWatch } from 'react-hook-form'

import { emptyItem, LIMITS, type ResumeFormValues } from '../form-schema'
import type { KindSpec } from '../sections/api'
import { itemAnchor } from './anchors'
import { CheckboxField, MonthField, TextAreaField, TextField } from './fields'
import { RowList } from './row-list'
import { ItemCard, SectionCard, SortableList, type SectionShell } from './section-card'
import { SECTION_ICONS } from './section-icons'

type EntryPath = `data.sections.${number}.entries.${number}`

function EntryHeading({ path, fallback }: { path: EntryPath; fallback: string }) {
  const [title, organization] = useWatch<ResumeFormValues>({ name: [`${path}.title`, `${path}.organization`] }) as [string, string]
  return [title, organization].filter(Boolean).join(' · ') || fallback
}

function DateFields({ path, mode }: { path: EntryPath; mode: 'range' | 'single' }) {
  const { setValue } = useFormContext<ResumeFormValues>()
  const isCurrent = useWatch<ResumeFormValues>({ name: `${path}.is_current` }) as boolean
  if (mode === 'single') return <MonthField name={`${path}.start_date`} label="Date" className="sm:max-w-[50%]" />
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <MonthField name={`${path}.start_date`} label="Start" />
      <MonthField name={`${path}.end_date`} label="End" disabled={isCurrent} hint={isCurrent ? 'Present' : undefined} />
      <div className="sm:col-span-2">
        <CheckboxField
          name={`${path}.is_current`}
          label="This is ongoing"
          onCheckedChange={(checked) => {
            if (checked) setValue(`${path}.end_date`, '', { shouldValidate: true })
          }}
        />
      </div>
    </div>
  )
}

/** A non-core section (clinical experience, publications, languages...). Which fields
 * show, and their labels, come from the section catalog. */
export function GenericSection({ shell, index, spec }: { shell: SectionShell; index: number; spec: KindSpec }) {
  const { control } = useFormContext<ResumeFormValues>()
  const { fields, append, remove, move } = useFieldArray({ control, name: `data.sections.${index}.entries` })
  const f = spec.fields
  if (!f) return null
  const noun = spec.item_label
  return (
    <SectionCard
      {...shell}
      icon={SECTION_ICONS[spec.kind]}
      description={spec.hint ?? undefined}
      onAdd={() => append(emptyItem.sectionItem())}
      max={LIMITS.entries}
      count={fields.length}
      addLabel={`Add ${noun}`}
    >
      <SortableList ids={fields.map((field) => field.id)} labelOf={(i) => `${noun} ${i + 1}`} onMove={move}>
        {fields.map((field, i) => {
          const path: EntryPath = `data.sections.${index}.entries.${i}`
          const label = `${noun} ${i + 1}`
          return (
            <ItemCard
              key={field.id}
              sortId={field.id}
              anchorId={itemAnchor(shell.id, i)}
              heading={<EntryHeading path={path} fallback={label[0].toUpperCase() + label.slice(1)} />}
              label={label}
              index={i}
              onRemove={remove}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <TextField
                  name={`${path}.title`}
                  label={f.title.label}
                  placeholder={f.title.placeholder ?? undefined}
                  className={f.organization ? undefined : 'sm:col-span-2'}
                />
                {f.organization && (
                  <TextField name={`${path}.organization`} label={f.organization.label} placeholder={f.organization.placeholder ?? undefined} />
                )}
                {f.location && (
                  <TextField
                    name={`${path}.location`}
                    label={f.location.label}
                    placeholder={f.location.placeholder ?? undefined}
                    className="sm:col-span-2"
                  />
                )}
              </div>
              {f.dates && <DateFields path={path} mode={f.dates} />}
              {f.description && (
                <TextAreaField name={`${path}.description`} label={f.description.label} placeholder={f.description.placeholder ?? undefined} rows={2} />
              )}
              {f.link && <TextField name={`${path}.link`} label={f.link.label} placeholder={f.link.placeholder ?? undefined} />}
              {f.bullets && (
                <RowList
                  name={`${path}.bullets`}
                  context={label}
                  label={f.bullets.label}
                  itemLabel="Point"
                  addLabel="Add point"
                  placeholder={f.bullets.placeholder ?? undefined}
                />
              )}
            </ItemCard>
          )
        })}
      </SortableList>
    </SectionCard>
  )
}
