import { useMemo, useState } from 'react'
import { Activity, Radio } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { TooltipProvider } from '@/components/ui/tooltip'
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
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-[1600px] space-y-8 px-5 py-8 sm:px-8 lg:px-10">
        <header className="flex flex-col justify-between gap-5 border-b border-zinc-800 pb-7 md:flex-row md:items-end">
          <div>
            <div className="mb-3 flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-400/10"><Activity className="size-5 text-cyan-300" /></div>
              <Badge className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300"><Radio className="size-3 animate-pulse" /> Live Demo</Badge>
            </div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Weir <span className="text-zinc-500">/</span> Admission Control</h1>
            <p className="mt-2 max-w-2xl text-sm text-zinc-500">Capacity governance for human approval workflows — pressure, bounded queues, and explainable interventions.</p>
          </div>
          <div className="font-mono text-xs uppercase tracking-[0.2em] text-zinc-600">Pressure → Queue → Agent → Policy → Ledger</div>
        </header>

        <div className="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 lg:flex-row lg:items-center lg:justify-between">
          <DemoControls approverId={selectedApprover.id} requestClasses={state.requestClasses} dispatch={dispatch} onReset={() => setSelectedApproverId('approver-1')} />
        </div>

        <SummaryStrip state={state} />
        <Legend />

        <section>
          <div className="mb-4 flex items-center justify-between">
            <div><h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-400">Approver capacity</h2><p className="mt-1 text-sm text-zinc-600">Select a constrained resource to inspect its live queue.</p></div>
            <span className="font-mono text-xs text-zinc-600">{state.approvers.length} resources monitored</span>
          </div>
          <ApproverGrid approvers={state.approvers} selectedApproverId={selectedApprover.id} onSelect={setSelectedApproverId} />
        </section>

        <Separator className="bg-zinc-800" />

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(380px,0.8fr)]">
          <QueuePanel approver={selectedApprover} requestClasses={state.requestClasses} now={now} />
          <AgentPanel approver={selectedApprover} backupApprover={backupApprover} requestClasses={state.requestClasses} ledger={state.ledger} now={now} />
        </section>

        <DecisionLedger entries={state.ledger} />
      </div>
    </main>
  )
}

export default function App() {
  return <TooltipProvider><WeirProvider><Dashboard /></WeirProvider></TooltipProvider>
}
