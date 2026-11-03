import { Search, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import { SubmitButton } from '@/components/submit-button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { apiErrorMessage } from '@/features/auth/api-error'
import { FormError } from '@/features/auth/form-error'
import { cn } from '@/lib/utils'

import { useCreateProof, useProofs, useSkillsCatalog, useUploadProof, type UploadProofType } from './api'
import { PROOF_TYPE_ORDER, PROOF_TYPES } from './proof-types'
import type { ProofType } from './types'
import { LEVELS } from './verification-level'

const MAX_SKILLS = 5
const MAX_BYTES = 5 * 1024 * 1024
// Mirrors backend/app/services/github/urls.py closely enough for instant feedback.
const REPO_URL = /^(https?:\/\/)?(www\.)?github\.com\/[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9._-]+(\.git)?\/?(\/.*)?$/
const WEB_URL = /^(https?:\/\/)?[^\s/$.?#]+\.[^\s]+$/i
const DOI = /^(doi:\s*)?(https?:\/\/(dx\.)?doi\.org\/)?10\.\d{4,9}\/\S+$/i

interface AddProofFormProps {
  preselectSlug: string | null
  /** From the Skill Gap page: the proof type suggested for the skill. */
  preselectType?: ProofType | null
  bare?: boolean
}

export function AddProofForm({ preselectSlug, preselectType = null, bare = false }: AddProofFormProps) {
  const catalog = useSkillsCatalog()
  const skill = catalog.data?.find((s) => s.slug === preselectSlug)
  const suggested = skill?.proof_types ?? []
  const [picked, setPicked] = useState<ProofType | null>(null)
  const kind: ProofType = picked ?? preselectType ?? suggested[0] ?? 'certificate'
  const meta = PROOF_TYPES[kind]
  const [bothMode, setBothMode] = useState<'upload' | 'link'>('upload')
  // The skill's suggested types first, then the rest.
  const order = [...suggested, ...PROOF_TYPE_ORDER.filter((t) => !suggested.includes(t))]

  return (
    <div className={bare ? 'flex flex-col gap-5' : 'flex flex-col gap-5 rounded-xl border bg-card p-4 md:p-5'}>
      {!bare && (
        <div>
          <h2 className="font-semibold">Add proof</h2>
          <p className="text-sm text-muted-foreground">Show evidence for a skill. We check it and tell you honestly how far it was verified.</p>
        </div>
      )}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">
          What kind of proof?
          {skill && suggested.length > 0 && (
            <span className="font-normal text-muted-foreground"> Best for {skill.name}: {PROOF_TYPES[suggested[0]].label.toLowerCase()}</span>
          )}
        </legend>
        <RadioGroup value={kind} onValueChange={(v) => setPicked(v as ProofType)} className="grid grid-cols-2 gap-2">
          {order.map((type) => {
            const m = PROOF_TYPES[type]
            const Icon = m.icon
            return (
              <Label
                key={type}
                htmlFor={`proof-type-${type}`}
                className="flex cursor-pointer items-start gap-2.5 rounded-lg border p-2.5 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5"
              >
                <RadioGroupItem id={`proof-type-${type}`} value={type} className="mt-0.5" />
                <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-medium">{m.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {suggested.includes(type) ? 'Suggested · ' : ''}Up to {LEVELS[m.ceiling].label.toLowerCase()}
                  </span>
                </span>
              </Label>
            )
          })}
        </RadioGroup>
      </fieldset>
      <div className="flex flex-col gap-1 rounded-lg bg-muted/50 px-3 py-2.5 text-sm">
        <p>{meta.how}</p>
        {meta.ceilingWhy && (
          <p className="text-xs text-muted-foreground">
            Counts as {LEVELS[meta.ceiling].label.toLowerCase()} at most: {meta.ceilingWhy}.
          </p>
        )}
      </div>

      {meta.input === 'both' && (
        <div className="flex w-fit rounded-lg border bg-muted p-1">
          <button
            type="button"
            className={cn('rounded-md px-3 py-1 text-sm font-medium transition-colors', bothMode === 'upload' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
            onClick={() => setBothMode('upload')}
          >
            Upload File
          </button>
          <button
            type="button"
            className={cn('rounded-md px-3 py-1 text-sm font-medium transition-colors', bothMode === 'link' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
            onClick={() => setBothMode('link')}
          >
            Paste Link
          </button>
        </div>
      )}

      {kind === 'github_repo' ? (
        <RepoForm key={kind} preselectSlug={preselectSlug} />
      ) : kind === 'live_link' ? (
        <LiveForm key={kind} />
      ) : kind === 'portfolio_link' || kind === 'publication' ? (
        <LinkForm key={kind} type={kind} preselectSlug={preselectSlug} />
      ) : meta.input === 'both' && bothMode === 'link' ? (
        <LinkForm key={`${kind}-link`} type={kind as 'certificate' | 'professional_license'} preselectSlug={preselectSlug} />
      ) : (
        <UploadForm key={`${kind}-upload`} type={kind as UploadProofType} preselectSlug={preselectSlug} />
      )}
    </div>
  )
}

function useSkillSelection(preselectSlug: string | null) {
  const catalog = useSkillsCatalog()
  const [picked, setPicked] = useState<string[] | null>(null)
  const preselected = catalog.data?.find((s) => s.slug === preselectSlug)
  const selected = picked ?? (preselected ? [preselected.id] : [])
  return { catalog, selected, setSelected: setPicked }
}

function SkillPicker({
  selection,
  label,
}: {
  selection: ReturnType<typeof useSkillSelection>
  label: string
}) {
  const { catalog, selected, setSelected } = selection
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (catalog.data ?? []).filter((s) => !q || s.name.toLowerCase().includes(q) || s.category.includes(q))
  }, [catalog.data, query])

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">
        {label} <span className="font-normal text-muted-foreground">({selected.length}/{MAX_SKILLS})</span>
      </legend>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input className="pl-8" placeholder="Search skills" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search skills" />
      </div>
      <ul className="grid max-h-48 gap-1 overflow-y-auto rounded-lg border p-2 sm:grid-cols-2">
        {catalog.isPending && <li className="text-sm text-muted-foreground">Loading skills…</li>}
        {filtered.map((skill) => {
          const checked = selected.includes(skill.id)
          const disabled = !checked && selected.length >= MAX_SKILLS
          return (
            <li key={skill.id}>
              <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted has-disabled:cursor-not-allowed has-disabled:opacity-50">
                <Checkbox
                  checked={checked}
                  disabled={disabled}
                  onCheckedChange={(on) =>
                    setSelected(on === true ? [...selected, skill.id].slice(0, MAX_SKILLS) : selected.filter((x) => x !== skill.id))
                  }
                />
                {skill.name}
              </label>
            </li>
          )
        })}
      </ul>
    </fieldset>
  )
}

function RepoForm({ preselectSlug }: { preselectSlug: string | null }) {
  const selection = useSkillSelection(preselectSlug)
  const create = useCreateProof()
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!REPO_URL.test(url.trim())) return setError('Enter a GitHub repository URL, like https://github.com/you/project.')
    if (selection.selected.length === 0) return setError('Choose at least one skill this repository proves.')
    try {
      const proof = await create.mutateAsync({ type: 'github_repo', url: url.trim(), skill_ids: selection.selected })
      navigate(`/proof-vault/${proof.id}`)
    } catch (err) {
      setError(apiErrorMessage(err, {}, { useServerDetail: true }))
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="proof-url">Repository URL</Label>
        <Input id="proof-url" inputMode="url" autoComplete="off" placeholder="https://github.com/you/project" value={url} onChange={(e) => setUrl(e.target.value)} />
        <p className="text-xs text-muted-foreground">Public repositories only.</p>
      </div>
      <SkillPicker selection={selection} label="Skills it proves" />
      <FormError message={error} />
      <SubmitButton pending={create.isPending} pendingText="Checking…" className="self-start">
        Submit for review
      </SubmitButton>
    </form>
  )
}

function UploadForm({ type, preselectSlug }: { type: UploadProofType; preselectSlug: string | null }) {
  const meta = PROOF_TYPES[type]
  const selection = useSkillSelection(preselectSlug)
  const upload = useUploadProof()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [registerUrl, setRegisterUrl] = useState('')
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const extensions = (meta.accept ?? '').split(',').filter((a) => a.startsWith('.'))
  const noun = meta.label.toLowerCase()

  const choose = (candidate: File | undefined) => {
    setError(null)
    if (!candidate) return
    const ext = candidate.name.toLowerCase().match(/\.[a-z]+$/)?.[0] ?? ''
    if (!extensions.includes(ext)) return setError(`Upload a ${meta.formats} file.`)
    if (candidate.size > MAX_BYTES) return setError(`That file is over 5 MB. Upload a smaller ${meta.formats} file.`)
    setFile(candidate)
  }

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!file) return setError(`Choose your ${noun} file.`)
    if (meta.skills === 'required' && selection.selected.length === 0) return setError('Choose at least one skill it shows.')
    if (registerUrl.trim() && !WEB_URL.test(registerUrl.trim())) return setError('Enter the full address of your register entry.')
    try {
      const proof = await upload.mutateAsync({ type, file, skillIds: selection.selected, registerUrl })
      navigate(`/proof-vault/${proof.id}`)
    } catch (err) {
      setError(apiErrorMessage(err, {}, { useServerDetail: true }))
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="flex flex-col gap-4">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]) }}
        className={cn(
          'flex flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
          dragging ? 'border-primary bg-primary/5' : 'hover:border-foreground/30',
        )}
      >
        <Upload className="size-6 text-muted-foreground" aria-hidden />
        <span className="font-medium">{file ? file.name : `Drag your ${noun} here, or click to browse`}</span>
        <span className="text-xs text-muted-foreground">{meta.formats}, up to 5 MB</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={meta.accept}
        className="sr-only"
        tabIndex={-1}
        aria-label={`${meta.label} file`}
        onChange={(e) => { choose(e.target.files?.[0]); e.target.value = '' }}
      />
      {type === 'professional_license' && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="register-url">Link to your public register entry (optional)</Label>
          <Input id="register-url" inputMode="url" autoComplete="off" placeholder="https://…" value={registerUrl} onChange={(e) => setRegisterUrl(e.target.value)} />
          <p className="text-xs text-muted-foreground">
            The page on your licensing body&apos;s website that shows your registration. Without it, the licence counts as self-reported.
          </p>
        </div>
      )}
      {type === 'work_sample' && (
        <p className="text-xs text-muted-foreground">Remove confidential, client or patient details before uploading.</p>
      )}
      <SkillPicker
        selection={selection}
        label={meta.skills === 'required' ? 'Skills it shows' : 'Skills (optional, we find them for you)'}
      />
      <FormError message={error} />
      <SubmitButton pending={upload.isPending} pendingText="Uploading…" className="self-start">
        Upload {noun}
      </SubmitButton>
    </form>
  )
}

function LinkForm({ type, preselectSlug }: { type: 'portfolio_link' | 'publication' | 'certificate' | 'professional_license'; preselectSlug: string | null }) {
  const selection = useSkillSelection(preselectSlug)
  const create = useCreateProof()
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const publication = type === 'publication'
  const certificate = type === 'certificate' || type === 'professional_license'

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    const value = url.trim()
    if (publication ? !(DOI.test(value) || WEB_URL.test(value)) : !WEB_URL.test(value)) {
      return setError(publication ? 'Enter a DOI (like 10.1234/abcd) or a link to the publication.' : certificate ? 'Enter a link to the certificate.' : 'Enter the full address of the page, like https://behance.net/you.')
    }
    if (selection.selected.length === 0) return setError('Choose at least one skill it shows.')
    try {
      const proof = await create.mutateAsync({ type, url: value, skill_ids: selection.selected })
      navigate(`/proof-vault/${proof.id}`)
    } catch (err) {
      setError(apiErrorMessage(err, {}, { useServerDetail: true }))
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="link-url">{publication ? 'DOI or link' : certificate ? 'Verification Link' : 'Page URL'}</Label>
        <Input
          id="link-url"
          inputMode="url"
          autoComplete="off"
          placeholder={publication ? '10.1234/abcd or https://…' : certificate ? 'https://coursera.org/verify/123' : 'https://behance.net/you'}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          {publication ? 'A DOI can be fully verified; a plain link at most partially.' : certificate ? 'We will visit this link to check the certificate.' : 'Make sure your name appears on the page.'}
        </p>
      </div>
      <SkillPicker selection={selection} label="Skills it shows" />
      <FormError message={error} />
      <SubmitButton pending={create.isPending} pendingText="Checking…" className="self-start">
        {publication ? 'Check publication' : certificate ? 'Check certificate' : 'Check portfolio'}
      </SubmitButton>
    </form>
  )
}

function LiveForm() {
  const proofs = useProofs()
  const create = useCreateProof()
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [linked, setLinked] = useState<string>('none')
  const [error, setError] = useState<string | null>(null)
  const repos = (proofs.data ?? []).filter((p) => p.type === 'github_repo')

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    if (!WEB_URL.test(url.trim())) return setError('Enter the full address of your live project, like https://myproject.dev.')
    try {
      const proof = await create.mutateAsync({
        type: 'live_link',
        url: url.trim(),
        skill_ids: [],
        linked_proof_id: linked === 'none' ? null : linked,
      })
      navigate(`/proof-vault/${proof.id}`)
    } catch (err) {
      setError(apiErrorMessage(err, {}, { useServerDetail: true }))
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="live-url">Live URL</Label>
        <Input id="live-url" inputMode="url" autoComplete="off" placeholder="https://myproject.dev" value={url} onChange={(e) => setUrl(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="live-repo">Built from (optional)</Label>
        <Select value={linked} onValueChange={setLinked}>
          <SelectTrigger id="live-repo" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Not linked to a repo</SelectItem>
            {repos.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.url?.replace('https://github.com/', '')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {repos.length === 0 && <p className="text-xs text-muted-foreground">Add the GitHub repo first to link it here.</p>}
      </div>
      <FormError message={error} />
      <SubmitButton pending={create.isPending} pendingText="Checking site…" className="self-start">
        Check site
      </SubmitButton>
    </form>
  )
}