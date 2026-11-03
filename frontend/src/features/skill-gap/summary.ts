import type { SkillGapReport } from './types'

/** "You're 56% ready for X. 2 critical skills are missing: Git and HTML/CSS." */
export function gapSummary(report: SkillGapReport): string {
  const lead = `You’re ${report.readiness}% ready for ${report.role.name}.`
  const missing = report.missing_critical
  if (missing.length > 0) {
    const names = missing.length === 1 ? missing[0] : `${missing.slice(0, -1).join(', ')} and ${missing[missing.length - 1]}`
    return `${lead} ${missing.length === 1 ? '1 critical skill is' : `${missing.length} critical skills are`} missing: ${names}.`
  }
  const toProve = report.counts.present_unverified + report.counts.inferred
  if (report.counts.missing > 0) return `${lead} No critical gaps. Close the remaining ${report.counts.missing} to stand out.`
  if (toProve > 0) return `${lead} Nothing is missing. Prove ${toProve} more skill${toProve === 1 ? '' : 's'} to reach 100%.`
  return `${lead} Every skill is verified.`
}
