import { useAuth } from '@/features/auth/use-auth'
import { BeforeAfter } from '@/features/landing/before-after'
import { FinalCta, LandingFooter, LandingHeader } from '@/features/landing/chrome'
import { Faq } from '@/features/landing/faq'
import { Features } from '@/features/landing/features'
import { Hero } from '@/features/landing/hero'
import { HowItWorks } from '@/features/landing/how-it-works'
import { LandingMotion } from '@/features/landing/motion'
import { useDocumentTitle } from '@/lib/use-document-title'

// Both CTAs lead to the resumes page, opening the matching dialog. Signed-out visitors
// create an account first and are sent on afterwards.
const BUILD = '/resumes?new=1'
const SCORE = '/resumes?import=1' // scoring starts from the resume you already have

export function LandingPage() {
  const { status } = useAuth()
  useDocumentTitle('Pass the ATS and prove your skills')
  const signedIn = status === 'authenticated'
  const via = (path: string) => (signedIn ? path : `/register?next=${encodeURIComponent(path)}`)

  return (
    <LandingMotion>
      <div className="flex min-h-svh flex-col overflow-x-clip bg-background">
        <LandingHeader signedIn={signedIn} startHref={via(BUILD)} />
        <main className="flex-1">
          <Hero buildHref={via(BUILD)} scoreHref={via(SCORE)} />
          <HowItWorks />
          <Features />
          <BeforeAfter />
          <Faq />
          <FinalCta buildHref={via(BUILD)} scoreHref={via(SCORE)} />
        </main>
        <LandingFooter signedIn={signedIn} />
      </div>
    </LandingMotion>
  )
}
