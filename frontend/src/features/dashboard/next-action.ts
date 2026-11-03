import type { NextAction } from '@/features/roadmap/types'

/** Where each next best action takes the user. */
export function nextActionHref(action: NextAction): string {
  const resume = action.resume_id
  switch (action.kind) {
    case 'create_resume':
      return '/resumes'
    case 'continue_skill':
    case 'close_gap':
      return `/roadmap?resume=${resume}#roadmap-${action.skill_slug}`
    case 'prove_skill':
      return `/proof-vault?skill=${action.skill_slug}`
    case 'run_ats':
    case 'improve_ats':
      return `/resumes/${resume}?ats=open`
    default:
      return `/resumes/${resume}`
  }
}
