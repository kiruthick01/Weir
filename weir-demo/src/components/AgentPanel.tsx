import { CheckCircle2, BrainCircuit, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { runGovernanceAgent, retryRejectedProposal, validateProposal } from '@/lib/agent'
import type { Approver, LedgerEntry, RequestClass } from '@/lib/types'
import { cn } from '@/lib/utils'

const actionStyles = { delegate: 'border-blue-500/40 bg-blue-500/15 text-blue-300', auto_approve: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300', escalate_to_human: 'border-amber-500/40 bg-amber-500/15 text-amber-300', hold: 'border-zinc-500/40 bg-zinc-500/15 text-zinc-300' }

export function AgentPanel({ approver, backupApprover, requestClasses, ledger, now }: { approver: Approver; backupApprover?: Approver; requestClasses: RequestClass[]; ledger: LedgerEntry[]; now: number }) {
  if (approver.pressureState !== 'critical') return null
  const proposals = runGovernanceAgent(approver, requestClasses, now, backupApprover)

  return (
    <Card className="border-red-500/30 bg-zinc-900/80">
      <CardHeader><CardTitle className="flex items-center gap-2 text-lg"><BrainCircuit className="size-5 text-red-300" /> Governance Agent <span className="text-sm font-normal text-zinc-500">Observe → Reason → Propose</span></CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {proposals.length === 0 ? <p className="text-sm text-zinc-500">Agent observing. No request has crossed 50% of its max-wait yet.</p> : proposals.map((proposal) => {
          const request = approver.queue.find((item) => item.requestId === proposal.requestId)
          const requestClass = request && requestClasses.find((item) => item.name === request.className)
          if (!request || !requestClass) return null
          const result = validateProposal(proposal, request, requestClass, approver, ledger, now)
          const retry = result.ok ? null : retryRejectedProposal(proposal, result.reason)
          return <div key={proposal.requestId} className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-xs text-zinc-400">{proposal.requestId}</span><Badge className={cn('border', actionStyles[proposal.kind])}>{proposal.kind.replaceAll('_', ' ')}</Badge></div>
            <p className="mt-3 text-sm leading-6 text-zinc-300">{proposal.reason}</p>
            <div className={cn('mt-3 flex items-start gap-2 border-t border-zinc-800 pt-3 text-sm', result.ok ? 'text-emerald-300' : 'text-red-300')}>
              {result.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
              <span>{result.ok ? 'Validated' : result.reason}</span>
            </div>
            {!result.ok && retry && <p className="mt-2 border-l border-amber-500/50 pl-3 text-sm text-amber-300"><span className="font-semibold">Retry:</span> {retry.kind.replaceAll('_', ' ')} — {retry.reason}</p>}
          </div>
        })}
      </CardContent>
    </Card>
  )
}
