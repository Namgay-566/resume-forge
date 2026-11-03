import { useFieldArray, useFormContext, useWatch } from 'react-hook-form'

import {
  AlignLeft,
  Award,
  BriefcaseBusiness,
  FolderGit2,
  GraduationCap,
  Layers,
  ShieldCheck,
  Trophy,
  UserRound,
} from 'lucide-react'

import { Input } from '@/components/ui/input'
import { SummaryGenerate } from '@/features/writing/summary-generate'
import { findPlaceholders } from '@/features/writing/diff'

import { emptyItem, LIMITS, type ResumeFormValues } from '../form-schema'
import { itemAnchor } from './anchors'
import { ProfileLinksField } from './profile-links'
import { useEditor } from './editor-context'
import { CheckboxField, MonthField, TextAreaField, TextField } from './fields'
import { RowList } from './row-list'
import { ItemCard, ItemControls, SectionCard, SortableList, type SectionShell } from './section-card'

function useForm() {
  return useFormContext<ResumeFormValues>()
}

/** Item heading built from its fields, e.g. "Engineer · Acme". */
function headingText(parts: (string | undefined)[], fallback: string) {
  return parts.filter(Boolean).join(' · ') || fallback
}

// --- Personal info -----------------------------------------------------------

export function PersonalInfoSection() {
  return (
    <SectionCard id="personal-info" title="Personal info" icon={UserRound}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField name="data.personal_info.full_name" label="Full name" autoComplete="name" />
        <TextField
          name="data.personal_info.headline"
          label="Headline"
          placeholder="e.g. Registered Nurse, Sales Executive"
        />
        <TextField name="data.personal_info.email" label="Email" type="email" autoComplete="email" />
        <TextField name="data.personal_info.phone" label="Phone" type="tel" autoComplete="tel" />
        <TextField
          name="data.personal_info.location"
          label="Location"
          placeholder="City, Country"
          className="sm:col-span-2"
        />
      </div>
      <ProfileLinksField />
    </SectionCard>
  )
}

// --- Summary -------------------------------------------------------------------

export function SummarySection({ shell }: { shell: SectionShell }) {
  const summary = useWatch<ResumeFormValues, 'data.summary'>({ name: 'data.summary' })
  return (
    <SectionCard
      {...shell}
      icon={AlignLeft}
      description="Two or three sentences on who you are and what you're aiming for."
    >
      <TextAreaField
        name="data.summary"
        label="Professional summary"
        rows={4}
        hint={`${summary.length} / 2000`}
      />
      {findPlaceholders(summary).length > 0 && (
        <p className="-mt-2 text-xs text-warning-text">
          Replace {findPlaceholders(summary).join(', ')} with your real number.
        </p>
      )}
      <SummaryGenerate />
    </SectionCard>
  )
}

// --- Experience ------------------------------------------------------------------

function ExperienceHeading({ index }: { index: number }) {
  const [title, company] = useWatch<ResumeFormValues>({
    name: [`data.experience.${index}.title`, `data.experience.${index}.company`],
  }) as [string, string]
  return headingText([title, company], `Position ${index + 1}`)
}

function DateRangeFields({ prefix }: { prefix: `data.${'experience' | 'education'}.${number}` }) {
  const { setValue } = useForm()
  const isCurrent = useWatch<ResumeFormValues>({ name: `${prefix}.is_current` }) as boolean
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <MonthField name={`${prefix}.start_date`} label="Start" />
      <MonthField name={`${prefix}.end_date`} label="End" disabled={isCurrent} hint={isCurrent ? 'Present' : undefined} />
      <div className="sm:col-span-2">
        <CheckboxField
          name={`${prefix}.is_current`}
          label={prefix.includes('education') ? 'I currently study here' : 'I currently work here'}
          onCheckedChange={(checked) => {
            if (checked) setValue(`${prefix}.end_date`, '', { shouldValidate: true })
          }}
        />
      </div>
    </div>
  )
}

export function ExperienceSection({ shell }: { shell: SectionShell }) {
  const { control } = useForm()
  const { fields, append, remove, move } = useFieldArray({ control, name: 'data.experience' })
  return (
    <SectionCard
      {...shell}
      icon={BriefcaseBusiness}
      description="Most recent first. Start bullets with a verb and include numbers where you can."
      onAdd={() => append(emptyItem.experience())}
      max={LIMITS.entries}
      count={fields.length}
      addLabel="Add position"
    >
      <SortableList ids={fields.map((f) => f.id)} labelOf={(i) => `position ${i + 1}`} onMove={move}>
      {fields.map((field, index) => (
        <ItemCard
          key={field.id}
          sortId={field.id}
          anchorId={itemAnchor('experience', index)}
          heading={<ExperienceHeading index={index} />}
          label={`position ${index + 1}`}
          index={index}
          onRemove={remove}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField name={`data.experience.${index}.title`} label="Job title" />
            <TextField name={`data.experience.${index}.company`} label="Company" />
            <TextField name={`data.experience.${index}.location`} label="Location" className="sm:col-span-2" />
          </div>
          <DateRangeFields prefix={`data.experience.${index}`} />
          <RowList
            name={`data.experience.${index}.bullets`}
            context={`Position ${index + 1}`}
            label="Highlights"
            itemLabel="Highlight"
            addLabel="Add bullet"
            placeholder="Trained 5 new starters, cutting their time to full productivity by 2 weeks"
          />
          <TextField
            name={`data.experience.${index}.tools_and_skills`}
            label="Tools & methods"
            placeholder="e.g. Excel, Salesforce, electronic health records"
            hint="Separate with commas"
          />
        </ItemCard>
      ))}
      </SortableList>
    </SectionCard>
  )
}

// --- Education -------------------------------------------------------------------

function EducationHeading({ index }: { index: number }) {
  const [degree, institution] = useWatch<ResumeFormValues>({
    name: [`data.education.${index}.degree`, `data.education.${index}.institution`],
  }) as [string, string]
  return headingText([degree, institution], `Education ${index + 1}`)
}

export function EducationSection({ shell }: { shell: SectionShell }) {
  const { control } = useForm()
  const { fields, append, remove, move } = useFieldArray({ control, name: 'data.education' })
  return (
    <SectionCard
      {...shell}
      icon={GraduationCap}
      onAdd={() => append(emptyItem.education())}
      max={LIMITS.education}
      count={fields.length}
      addLabel="Add education"
    >
      <SortableList ids={fields.map((f) => f.id)} labelOf={(i) => `education ${i + 1}`} onMove={move}>
      {fields.map((field, index) => (
        <ItemCard
          key={field.id}
          sortId={field.id}
          anchorId={itemAnchor('education', index)}
          heading={<EducationHeading index={index} />}
          label={`education ${index + 1}`}
          index={index}
          onRemove={remove}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField name={`data.education.${index}.institution`} label="Institution" className="sm:col-span-2" />
            <TextField name={`data.education.${index}.degree`} label="Degree" placeholder="BSc" />
            <TextField name={`data.education.${index}.field_of_study`} label="Field of study" />
            <TextField name={`data.education.${index}.grade`} label="Grade" placeholder="3.8 GPA" />
          </div>
          <DateRangeFields prefix={`data.education.${index}`} />
          <RowList
            name={`data.education.${index}.bullets`}
            context={`Education ${index + 1}`}
            label="Details"
            itemLabel="Detail"
            addLabel="Add detail"
            placeholder="Dissertation on patient safety in night shifts"
          />
        </ItemCard>
      ))}
      </SortableList>
    </SectionCard>
  )
}

// --- Projects --------------------------------------------------------------------

function ProjectHeading({ index }: { index: number }) {
  const name = useWatch<ResumeFormValues>({ name: `data.projects.${index}.name` }) as string
  return headingText([name], `Project ${index + 1}`)
}

export function ProjectsSection({ shell }: { shell: SectionShell }) {
  const { control } = useForm()
  const { fields, append, remove, move } = useFieldArray({ control, name: 'data.projects' })
  return (
    <SectionCard
      {...shell}
      icon={FolderGit2}
      description="Coursework, personal or work projects that show what you can do. Link each to proof in your Proof Vault."
      onAdd={() => append(emptyItem.projects())}
      max={LIMITS.entries}
      count={fields.length}
      addLabel="Add project"
    >
      <SortableList ids={fields.map((f) => f.id)} labelOf={(i) => `project ${i + 1}`} onMove={move}>
      {fields.map((field, index) => (
        <ItemCard
          key={field.id}
          sortId={field.id}
          anchorId={itemAnchor('projects', index)}
          heading={<ProjectHeading index={index} />}
          label={`project ${index + 1}`}
          index={index}
          onRemove={remove}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField name={`data.projects.${index}.name`} label="Project name" />
            <TextField name={`data.projects.${index}.link`} label="Link" placeholder="yourportfolio.com/project" />
          </div>
          <TextAreaField name={`data.projects.${index}.description`} label="Description" rows={2} />
          <RowList
            name={`data.projects.${index}.bullets`}
            context={`Project ${index + 1}`}
            label="Highlights"
            itemLabel="Highlight"
            addLabel="Add bullet"
          />
          <TextField
            name={`data.projects.${index}.tools_and_skills`}
            label="Tools & methods"
            placeholder="e.g. Canva, SPSS, AutoCAD"
            hint="Separate with commas"
          />
        </ItemCard>
      ))}
      </SortableList>
    </SectionCard>
  )
}

// --- Skills ----------------------------------------------------------------------

function VerifiedMark({ index }: { index: number }) {
  const { proofLinks } = useEditor()
  const proofId = useWatch<ResumeFormValues>({ name: `data.skills.${index}.proof_id` }) as string | null
  if (!proofId || !proofLinks[proofId]?.verified) return null
  return <ShieldCheck className="size-4 shrink-0 text-success-text" aria-label="Verified by a proof" />
}

export function SkillsSection({ shell }: { shell: SectionShell }) {
  const { control, register } = useForm()
  const { fields, append, remove, move } = useFieldArray({ control, name: 'data.skills' })
  return (
    <SectionCard
      {...shell}
      icon={Layers}
      description="One skill per row. Use the name employers put in job adverts (e.g. “Patient assessment”, “Excel”, “Lesson planning”)."
      onAdd={() => append(emptyItem.skills())}
      max={LIMITS.skills}
      count={fields.length}
      addLabel="Add skill"
    >
      {fields.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2">
          {fields.map((field, index) => (
            <li key={field.id} id={itemAnchor('skills', index)} className="flex items-center gap-1">
              <label htmlFor={`skill-${field.id}`} className="sr-only">
                Skill {index + 1}
              </label>
              <VerifiedMark index={index} />
              <Input
                id={`skill-${field.id}`}
                placeholder="Skill"
                {...register(`data.skills.${index}.name`)}
              />
              <ItemControls
                index={index}
                total={fields.length}
                label={`skill ${index + 1}`}
                onMove={move}
                onRemove={remove}
              />
            </li>
          ))}
        </ul>
      )}
      <CheckboxField
        name="data.show_verified_skills"
        label="Add a “Verified skills” line with proof links (skills marked with a shield)"
      />
    </SectionCard>
  )
}

// --- Certifications ----------------------------------------------------------------

function CertificationHeading({ index }: { index: number }) {
  const name = useWatch<ResumeFormValues>({ name: `data.certifications.${index}.name` }) as string
  return headingText([name], `Certification ${index + 1}`)
}

export function CertificationsSection({ shell }: { shell: SectionShell }) {
  const { control } = useForm()
  const { fields, append, remove, move } = useFieldArray({ control, name: 'data.certifications' })
  return (
    <SectionCard
      {...shell}
      icon={Award}
      onAdd={() => append(emptyItem.certifications())}
      max={LIMITS.certifications}
      count={fields.length}
      addLabel="Add certification"
    >
      <SortableList ids={fields.map((f) => f.id)} labelOf={(i) => `certification ${i + 1}`} onMove={move}>
      {fields.map((field, index) => (
        <ItemCard
          key={field.id}
          sortId={field.id}
          anchorId={itemAnchor('certifications', index)}
          heading={<CertificationHeading index={index} />}
          label={`certification ${index + 1}`}
          index={index}
          onRemove={remove}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField name={`data.certifications.${index}.name`} label="Name" className="sm:col-span-2" />
            <TextField name={`data.certifications.${index}.issuer`} label="Issuer" />
            <MonthField name={`data.certifications.${index}.issue_date`} label="Issued" />
            <TextField name={`data.certifications.${index}.credential_id`} label="Credential ID" />
            <TextField
              name={`data.certifications.${index}.credential_url`}
              label="Credential URL"
              className="sm:col-span-2"
            />
          </div>
        </ItemCard>
      ))}
      </SortableList>
    </SectionCard>
  )
}

// --- Achievements --------------------------------------------------------------------

export function AchievementsSection({ shell }: { shell: SectionShell }) {
  return (
    <SectionCard {...shell} icon={Trophy} description="Results you're proud of that don't fit under a single job.">
      <RowList
        name="data.achievements"
        label="Achievements"
        itemLabel="Achievement"
        addLabel="Add achievement"
        placeholder="Employee of the Quarter, Q2 2024"
      />
    </SectionCard>
  )
}
