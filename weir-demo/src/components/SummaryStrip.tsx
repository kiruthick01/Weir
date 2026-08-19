import { Badge } from '@/components/ui/badge'
import type { DecisionOutcome, PressureState, WeirState } from '@/lib/types'

const outcomes: DecisionOutcome[] = ['queued', 'delegated', 'auto_approved', 'manually_approved', 'timed_out', 'rejected_proposal']
const pressures: PressureState[] = ['normal', 'elevated', 'critical']
const outcomeStyles: Record<DecisionOutcome, string> = {
  queued: 'border-slate-500/30 bg-slate-500/15 text-slate-300',
  delegated: 'border-blue-500/30 bg-blue-500/15 text-blue-300',
  auto_approved: 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300',
  manually_approved: 'border-teal-500/30 bg-teal-500/15 text-teal-300',
  timed_out: 'border-red-500/30 bg-red-500/15 text-red-300',
  rejected_proposal: 'border-orange-500/50 bg-orange-500/10 text-orange-300',
}

export function SummaryStrip({ state }: { state: WeirState }) {
  const totalRequests = new Set(state.ledger.map((entry) => entry.requestId)).size
  const countOutcome = (outcome: DecisionOutcome) => state.ledger.filter((entry) => entry.outcome === outcome).length
  const countPressure = (pressure: PressureState) => state.approvers.filter((approver) => approver.pressureState === pressure).length

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-3 font-mono text-xs">
      <div><span className="text-zinc-500">requests </span><span className="text-lg text-zinc-100">{totalRequests}</span></div>
      <div className="flex flex-wrap items-center gap-1.5"><span className="mr-1 text-zinc-500">outcomes</span>{outcomes.map((outcome) => <Badge key={outcome} className={`border ${outcomeStyles[outcome]}`}>{outcome.replace('_', ' ')} {countOutcome(outcome)}</Badge>)}</div>
      <div className="flex items-center gap-2"><span className="text-zinc-500">pressure</span>{pressures.map((pressure) => <span key={pressure} className="text-zinc-300"><span className={`mr-1 inline-block size-2 rounded-full ${pressure === 'normal' ? 'bg-emerald-400' : pressure === 'elevated' ? 'bg-amber-400' : 'bg-red-400'}`} />{countPressure(pressure)}</span>)}</div>
    </div>
  )
}
