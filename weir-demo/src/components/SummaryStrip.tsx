import type { DecisionOutcome, PressureState, WeirState } from '@/lib/types'

const outcomes: DecisionOutcome[] = ['queued', 'delegated', 'auto_approved', 'manually_approved', 'timed_out', 'rejected_proposal']
const pressures: PressureState[] = ['normal', 'elevated', 'critical']

export function SummaryStrip({ state }: { state: WeirState }) {
  const totalRequests = new Set(state.ledger.map((entry) => entry.requestId)).size
  const countOutcome = (outcome: DecisionOutcome) => state.ledger.filter((entry) => entry.outcome === outcome).length
  const countPressure = (pressure: PressureState) => state.approvers.filter((approver) => approver.pressureState === pressure).length

  return (
    <div className="grid grid-cols-2 border-y-2 border-ink sm:grid-cols-4 lg:grid-cols-[repeat(4,minmax(0,1fr))_repeat(6,minmax(0,1fr))]">
      <div className="border-l border-line px-4 py-3 first:border-l-0">
        <div className="font-mono text-[10px] uppercase tracking-wide text-muted">Requests</div>
        <div className="mt-1 font-mono text-xl font-bold">{totalRequests}</div>
      </div>
      {pressures.map((pressure) => (
        <div key={pressure} className="border-l border-line px-4 py-3">
          <div className="font-mono text-[10px] uppercase tracking-wide text-muted">{pressure}</div>
          <div className={`mt-1 font-mono text-xl font-bold ${pressure === 'critical' ? 'text-accent' : ''}`}>{countPressure(pressure)}</div>
        </div>
      ))}
      {outcomes.map((outcome) => (
        <div key={outcome} className="border-l border-line px-4 py-3">
          <div className="font-mono text-[10px] uppercase tracking-wide text-muted">{outcome.replace('_', ' ')}</div>
          <div className={`mt-1 font-mono text-xl font-bold ${outcome === 'rejected_proposal' || outcome === 'timed_out' ? 'text-accent' : ''}`}>{countOutcome(outcome)}</div>
        </div>
      ))}
    </div>
  )
}
