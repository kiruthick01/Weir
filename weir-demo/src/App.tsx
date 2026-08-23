import { useMemo, useState } from 'react'
import { AgentPanel } from '@/components/AgentPanel'
import { ApproverGrid } from '@/components/ApproverGrid'
import { DecisionLedger } from '@/components/DecisionLedger'
import { DemoControls } from '@/components/DemoControls'
import { Legend } from '@/components/Legend'
import { QueuePanel } from '@/components/QueuePanel'
import { SummaryStrip } from '@/components/SummaryStrip'
import { WeirProvider } from '@/state/WeirProvider'
import { useWeir } from '@/state/useWeir'

function Dashboard() {
  const { state, dispatch } = useWeir()
  const [selectedApproverId, setSelectedApproverId] = useState(state.approvers[0]?.id ?? '')
  const selectedApprover = useMemo(() => state.approvers.find((approver) => approver.id === selectedApproverId) ?? state.approvers[0], [selectedApproverId, state.approvers])
  const backupApprover = state.approvers.find((approver) => approver.id === selectedApprover?.backupApproverId)
  const now = Date.now()

  if (!selectedApprover) return null

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto max-w-[1600px] space-y-8 px-5 py-8 sm:px-8 lg:px-10">
        <header className="flex flex-col justify-between gap-5 border-b-2 border-ink pb-6 md:flex-row md:items-end">
          <div>
            <div className="mb-2 font-mono text-xs uppercase tracking-[0.2em] text-accent">Live demo</div>
            <h1 className="text-3xl font-extrabold uppercase tracking-tight sm:text-4xl">Weir <span className="text-muted">/</span> Admission Control</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted">Capacity governance for human approval workflows — pressure, bounded queues, and explainable interventions.</p>
          </div>
          <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">Pressure {'->'} Queue {'->'} Agent {'->'} Policy {'->'} Ledger</div>
        </header>

        <div className="border border-line p-4">
          <DemoControls selectedApproverId={selectedApproverId} requestClasses={state.requestClasses} dispatch={dispatch} onReset={() => setSelectedApproverId('approver-1')} />
        </div>

        <SummaryStrip state={state} />
        <Legend />

        <section>
          <div className="mb-4 flex items-center justify-between border-t border-line pt-6">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-widest">Approver capacity</h2>
              <p className="mt-1 text-sm text-muted">Select a constrained resource to inspect its live queue.</p>
            </div>
            <span className="font-mono text-xs text-muted">{state.approvers.length} resources monitored</span>
          </div>
          <ApproverGrid approvers={state.approvers} selectedApproverId={selectedApprover.id} onSelect={setSelectedApproverId} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(380px,0.8fr)]">
          <QueuePanel approver={selectedApprover} now={now} />
          <AgentPanel approver={selectedApprover} backupApprover={backupApprover} requestClasses={state.requestClasses} ledger={state.ledger} now={now} />
        </section>

        <DecisionLedger entries={state.ledger} />
      </div>
    </main>
  )
}

export default function App() {
  return <WeirProvider><Dashboard /></WeirProvider>
}
