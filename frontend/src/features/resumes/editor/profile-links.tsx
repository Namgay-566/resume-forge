import { Plus, Trash2 } from 'lucide-react'
import { useFieldArray, useFormContext, useWatch } from 'react-hook-form'

import { LinkedInMark } from '@/components/icons/linkedin-mark'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/use-auth'
import { useTargetRoles } from '@/features/target-roles/api'

import { emptyItem, LIMITS, type ResumeFormValues } from '../form-schema'
import { useProfileLinkTypes } from '../sections/api'
import { TextField } from './fields'

const FALLBACK = ['LinkedIn', 'Personal website']

/** Profile and portfolio links (LinkedIn, GitHub, Behance, ORCID...). The ones suggested
 * come from the target role's industry, so a researcher is offered ORCID and a designer
 * Behance, instead of everyone being asked for GitHub. */
export function ProfileLinksField() {
  const { control, setFocus } = useFormContext<ResumeFormValues>()
  const { fields, append, remove } = useFieldArray({ control, name: 'data.personal_info.profile_links' })
  const [roleId, links] = useWatch<ResumeFormValues>({ name: ['target_role_id', 'data.personal_info.profile_links'] }) as [
    string | null,
    ResumeFormValues['data']['personal_info']['profile_links'],
  ]
  const industry = useTargetRoles().data?.find((r) => r.id === roleId)?.industry
  const types = useProfileLinkTypes().data ?? []
  const placeholder = (label: string) => types.find((t) => t.label.toLowerCase() === label.trim().toLowerCase())?.placeholder
  const have = new Set((links ?? []).map((l) => l.label.trim().toLowerCase()))
  const full = fields.length >= LIMITS.profileLinks
  // Signed in with LinkedIn: offer that profile first (with its URL once we know it).
  const { user } = useAuth()
  const offerLinkedIn = Boolean(user?.linkedin_connected) && !have.has('linkedin') && !full
  const linkedInUrl = user?.linkedin_url?.replace(/^(https?:\/\/)?(www\.)?/i, '').replace(/\/$/, '') ?? ''
  const suggested = (industry?.profile_links?.length ? industry.profile_links : FALLBACK).filter(
    (label) => !have.has(label.toLowerCase()) && !(offerLinkedIn && label.toLowerCase() === 'linkedin'),
  )

  const add = (label: string, url = '') => {
    append({ ...emptyItem.profileLink(label), url })
    // Focus the new row's address (or its name, for a custom link).
    const field = !label ? 'label' : url ? null : 'url'
    if (field) window.setTimeout(() => setFocus(`data.personal_info.profile_links.${fields.length}.${field}`), 0)
  }

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-1 text-sm font-medium">Profile links</legend>
      {fields.map((field, index) => {
        const label = links?.[index]?.label ?? ''
        return (
          <div key={field.id} className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto] sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto] items-start gap-2">
            <TextField name={`data.personal_info.profile_links.${index}.label`} label="Site" list="profile-link-types" placeholder="e.g. ORCID" />
            <TextField name={`data.personal_info.profile_links.${index}.url`} label="Address" placeholder={placeholder(label) ?? 'yoursite.com/you'} inputMode="url" />
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="mt-7 text-muted-foreground hover:bg-danger-muted hover:text-danger-text"
              aria-label={`Remove ${label || `link ${index + 1}`}`}
              onClick={() => remove(index)}
            >
              <Trash2 />
            </Button>
          </div>
        )
      })}
      <datalist id="profile-link-types">
        {types.map((t) => (
          <option key={t.label} value={t.label} />
        ))}
      </datalist>
      {offerLinkedIn && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border bg-muted/60 px-3 py-2 text-sm">
          <LinkedInMark className="size-4 shrink-0 text-[#0A66C2] dark:text-[#71B7FB]" aria-hidden />
          <p className="min-w-0 flex-1">
            {linkedInUrl
              ? 'Add the LinkedIn profile you signed in with?'
              : 'You signed in with LinkedIn. Add your public profile URL: LinkedIn doesn’t share it at sign-in.'}
          </p>
          <Button type="button" variant="outline" size="sm" className="bg-card" onClick={() => add('LinkedIn', linkedInUrl)}>
            <Plus /> {linkedInUrl ? `Add ${linkedInUrl}` : 'Add LinkedIn'}
          </Button>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {suggested.length > 0 && !full && (
          <span className="text-xs text-muted-foreground">{industry ? `Suggested for ${industry.name}:` : 'Suggested:'}</span>
        )}
        {!full &&
          suggested.map((label) => (
            <Button key={label} type="button" variant="outline" size="sm" onClick={() => add(label)}>
              <Plus /> {label}
            </Button>
          ))}
        {!full && (
          <Button type="button" variant="ghost" size="sm" onClick={() => add('')}>
            <Plus /> Other link
          </Button>
        )}
        {full && <p className="text-xs text-muted-foreground">That&apos;s the maximum ({LIMITS.profileLinks}).</p>}
      </div>
    </fieldset>
  )
}
