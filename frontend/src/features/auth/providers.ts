import { GitHubMark } from '@/components/icons/github-mark'
import { GoogleMark } from '@/components/icons/google-mark'
import { LinkedInMark } from '@/components/icons/linkedin-mark'

/** Sign-in providers, in the order shown. Each is a full-page navigation: the backend
 * redirects to the provider and back (see backend/app/api/routers/auth.py). */
export const PROVIDERS = [
  { id: 'google', label: 'Google', Icon: GoogleMark, iconClass: '' },
  { id: 'linkedin', label: 'LinkedIn', Icon: LinkedInMark, iconClass: 'text-[#0A66C2] dark:text-[#71B7FB]' },
  { id: 'github', label: 'GitHub', Icon: GitHubMark, iconClass: '' },
] as const
