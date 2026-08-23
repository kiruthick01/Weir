import { runGovernanceAgent, retryRejectedProposal, validateProposal } from '@/lib/agent'
import type { Approver, LedgerEntry, RequestClass } from '@/lib/types'

export function AgentPanel({ approver, backupApprover, requestClasses, ledger, now }: { approver: Approver; backupApprover?: Approver; requestClasses: RequestClass[]; ledger: LedgerEntry[]; now: number }) {
  if (approver.pressureState !== 'critical') return null
  const proposals = runGovernanceAgent(approver, requestClasses, now, backupApprover)

  return (
    <div className="border-2 border-accent">
      <div className="border-b-2 border-accent px-4 py-3">
        <h3 className="text-sm font-bold uppercase tracking-wide text-accent">Governance agent</h3>
        <p className="mt-0.5 font-mono text-xs text-muted">observe {'->'} reason {'->'} propose</p>
      </div>
      <div className="space-y-3 p-4">
        {proposals.length === 0 ? (
          <p className="text-sm italic text-muted">Agent observing. No request has crossed 50% of its max-wait yet.</p>
        ) : proposals.map((proposal) => {
          const request = approver.queue.find((item) => item.requestId === proposal.requestId)
          const requestClass = request && requestClasses.find((item) => item.name === request.className)
          if (!request || !requestClass) return null
          const result = validateProposal(proposal, request, requestClass, approver, ledger, now)
          const retry = result.ok ? null : retryRejectedProposal(proposal, result.reason)
          return (
            <div key={proposal.requestId} className="border border-line p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted">{proposal.requestId}</span>
                <span className="font-mono text-xs font-bold uppercase">{proposal.kind.replaceAll('_', ' ')}</span>
              </div>
              <p className="mt-3 text-sm leading-6">{proposal.reason}</p>
              <div className={`mt-3 border-t border-line pt-3 text-sm font-bold ${result.ok ? 'text-ink' : 'text-accent'}`}>
                {result.ok ? 'validated' : result.reason}
              </div>
              {!result.ok && retry && (
                <p className="mt-2 border-l-2 border-ink pl-3 text-sm">
                  <span className="font-bold">Retry:</span> {retry.kind.replaceAll('_', ' ')} — {retry.reason}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
