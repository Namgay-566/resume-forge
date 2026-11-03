import { Monitor, Moon, Sun } from 'lucide-react'

import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { User } from '@/features/auth/types'
import type { Theme } from '@/features/theme/theme'
import { useTheme } from '@/features/theme/use-theme'

import { useSavePreference } from './api'
import { isPlaceholderEmail } from './helpers'
import { SettingRow, SettingsSection } from './settings-section'

export function NotificationsSection({ user }: { user: User }) {
  const save = useSavePreference()
  const noEmail = isPlaceholderEmail(user.email)

  return (
    <SettingsSection
      id="notifications"
      title="Email notifications"
      description={
        noEmail
          ? 'Add an email address under Profile to get these.'
          : <>Sent to <span className="font-medium text-foreground">{user.email}</span>.</>
      }
    >
      <SettingRow
        label="Proof results"
        htmlFor="email-proof-updates"
        hint="When a proof is verified or needs more, and when a referee answers your request."
      >
        <Checkbox
          id="email-proof-updates"
          checked={user.preferences.email_proof_updates}
          onCheckedChange={(checked) => save({ email_proof_updates: checked === true })}
        />
      </SettingRow>
      <SettingRow
        label="Security notices"
        htmlFor="email-security"
        hint="When your password, email or sign-in methods change. Always on, so you hear about changes you didn’t make."
      >
        <Checkbox id="email-security" checked disabled />
      </SettingRow>
    </SettingsSection>
  )
}

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export function AppearanceSection() {
  const { theme, setTheme } = useTheme()

  return (
    <SettingsSection id="appearance" title="Appearance">
      <SettingRow label="Theme" hint="Saved on this device. System follows your computer or phone’s setting.">
        <RadioGroup
          value={theme}
          onValueChange={(value) => setTheme(value as Theme)}
          className="flex flex-wrap gap-2"
          aria-label="Theme"
        >
          {THEMES.map(({ value, label, icon: Icon }) => (
            <Label
              key={value}
              htmlFor={`theme-${value}`}
              className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 font-normal has-data-[state=checked]:border-primary has-data-[state=checked]:bg-primary/5"
            >
              <RadioGroupItem id={`theme-${value}`} value={value} className="sr-only" />
              <Icon className="size-4" aria-hidden />
              {label}
            </Label>
          ))}
        </RadioGroup>
      </SettingRow>
    </SettingsSection>
  )
}
