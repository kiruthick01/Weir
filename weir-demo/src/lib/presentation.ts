import type { DecisionOutcome, PressureState } from './types'

export const OUTCOMES: DecisionOutcome[] = ['queued', 'delegated', 'auto_approved', 'manually_approved', 'timed_out', 'rejected_proposal']
export const PRESSURES: PressureState[] = ['normal', 'elevated', 'critical']

export const outcomeLabels: Record<DecisionOutcome, string> = {
  queued: 'queued', delegated: 'delegated', auto_approved: 'auto-approved',
  manually_approved: 'manually approved', timed_out: 'timed out', rejected_proposal: 'rejected proposal',
}

export const outcomeStyles: Record<DecisionOutcome, string> = {
  queued: 'border-slate-500/30 bg-slate-500/15 text-slate-300', delegated: 'border-blue-500/30 bg-blue-500/15 text-blue-300',
  auto_approved: 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300', manually_approved: 'border-teal-500/30 bg-teal-500/15 text-teal-300',
  timed_out: 'border-red-500/30 bg-red-500/15 text-red-300', rejected_proposal: 'border-orange-500/50 bg-orange-500/10 text-orange-300',
}

export const pressureDotStyles: Record<PressureState, string> = {
  normal: 'bg-emerald-400', elevated: 'bg-amber-400', critical: 'bg-red-400',
}
