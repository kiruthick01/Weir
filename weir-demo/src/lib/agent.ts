/*
 * This is a fully simulated, deterministic TypeScript governance agent for
 * demo purposes. It stands in for a real Claude tool-use loop and performs
 * no live model calls, network requests, or API-key lookups. See
 * governance_agent.py in the runnable-codebase track for the real Claude
 * tool-use version.
 */

import type {
  Approver,
  DecisionOutcome,
  LedgerEntry,
  Proposal,
  QueuedRequest,
  RequestClass,
} from './types'

type BackupContext = Pick<Approver, 'id' | 'pressureState'>

const ledgerId = (now: number) =>
  `ledger-${now}-${Math.random().toString(36).slice(2, 8)}`

const proposalLabel = (proposal: Proposal) =>
  proposal.kind === 'auto_approve'
    ? 'auto-approval'
    : proposal.kind === 'delegate'
      ? 'delegation'
      : proposal.kind === 'escalate_to_human'
        ? 'human escalation'
        : 'hold'

export function runGovernanceAgent(
  approver: Approver,
  requestClasses: RequestClass[],
  now: number,
  backupApprover?: BackupContext,
): Proposal[] {
  if (approver.pressureState !== 'critical') return []

  const queueDepth = approver.queue.length
  const secondsInCritical = Math.max(0, (now - approver.stateSince) / 1000)

  return approver.queue.flatMap((request): Proposal[] => {
    const requestClass = requestClasses.find((item) => item.name === request.className)
    if (!requestClass) return []

    const elapsed = now - request.enqueuedAt
    const halfwayPoint = requestClass.maxWaitSeconds * 1000 * 0.5
    if (elapsed < halfwayPoint) return []

    const amount = request.amount
    const threshold = requestClass.autoApproveThreshold
    if (threshold !== null && amount <= threshold) {
      return [{
        requestId: request.requestId,
        kind: 'auto_approve' as const,
        reason: `Critical for ${secondsInCritical.toFixed(1)}s with queue depth ${queueDepth}; amount $${amount.toFixed(2)} is within the $${threshold.toFixed(2)} low-risk threshold after ${Math.floor(elapsed / 1000)}s waiting.`,
      }]
    }

    if (backupApprover?.pressureState !== 'critical') {
      return [{
        requestId: request.requestId,
        kind: 'delegate' as const,
        targetApproverId: backupApprover?.id ?? approver.backupApproverId,
        reason: `Critical for ${secondsInCritical.toFixed(1)}s with queue depth ${queueDepth}; amount $${amount.toFixed(2)} is not eligible for the $${threshold?.toFixed(2) ?? 'disabled'} auto-approval threshold, so it can move after ${Math.floor(elapsed / 1000)}s waiting.`,
      }]
    }

    return [{
      requestId: request.requestId,
      kind: 'escalate_to_human' as const,
      reason: `Critical for ${secondsInCritical.toFixed(1)}s with queue depth ${queueDepth}; amount $${amount.toFixed(2)} cannot auto-approve and backup ${approver.backupApproverId} is also critical after ${Math.floor(elapsed / 1000)}s waiting.`,
    }]
  })
}

export function validateProposal(
  proposal: Proposal,
  request: QueuedRequest,
  requestClass: RequestClass,
  approver: Approver,
  recentLedger: LedgerEntry[],
  now: number,
): { ok: boolean; reason: string } {
  if (proposal.kind === 'auto_approve' && requestClass.riskTier !== 'low') {
    return { ok: false, reason: `Auto-approval rejected: request risk tier is '${requestClass.riskTier}', but only 'low' risk requests are eligible.` }
  }

  if (proposal.kind === 'auto_approve' && (requestClass.autoApproveThreshold === null || request.amount > requestClass.autoApproveThreshold)) {
    return { ok: false, reason: `Auto-approval rejected: amount $${request.amount.toFixed(2)} exceeds threshold ${requestClass.autoApproveThreshold === null ? 'disabled (null)' : `$${requestClass.autoApproveThreshold.toFixed(2)}`}.` }
  }

  if (proposal.kind === 'delegate' && proposal.targetApproverId !== approver.backupApproverId) {
    return { ok: false, reason: `Delegation rejected: target '${proposal.targetApproverId ?? 'missing'}' is not the designated backup approver '${approver.backupApproverId}'.` }
  }

  if (proposal.kind === 'auto_approve') {
    const windowStart = now - 60_000
    const autoApprovals = recentLedger.filter((entry) =>
      entry.approverId === approver.id &&
      entry.outcome === 'auto_approved' &&
      entry.timestamp >= windowStart,
    ).length
    if (autoApprovals >= 3) {
      return { ok: false, reason: `Auto-approval rejected: approver already has ${autoApprovals} auto-approvals in the last 60 simulated seconds; limit is 3.` }
    }
  }

  return { ok: true, reason: `${proposalLabel(proposal)} passed deterministic policy validation.` }
}

export function retryRejectedProposal(
  original: Proposal,
  rejectionReason: string,
): Proposal | null {
  const reason = rejectionReason.toLowerCase()
  if (original.kind === 'auto_approve' && (reason.includes('risk') || reason.includes('amount') || reason.includes('threshold'))) {
    return { requestId: original.requestId, kind: 'escalate_to_human', reason: `Fallback after rejected auto-approval: ${rejectionReason}` }
  }
  if (reason.includes('rate') || reason.includes('limit') || reason.includes('last 60')) {
    return { requestId: original.requestId, kind: 'hold', reason: `Hold after rate-limit rejection; reconsider next cycle: ${rejectionReason}` }
  }
  if (original.kind === 'delegate' && reason.includes('target')) {
    return { requestId: original.requestId, kind: 'escalate_to_human', reason: `Fallback after invalid delegate target: ${rejectionReason}` }
  }
  return null
}

const outcomeFor = (kind: Proposal['kind']): DecisionOutcome | null => {
  if (kind === 'delegate') return 'delegated'
  if (kind === 'auto_approve') return 'auto_approved'
  if (kind === 'escalate_to_human') return 'queued'
  return null
}

const commit = (
  proposal: Proposal,
  outcome: DecisionOutcome,
  approver: Approver,
  now: number,
  reason: string,
): LedgerEntry => ({
  id: ledgerId(now),
  timestamp: now,
  approverId: approver.id,
  requestId: proposal.requestId,
  outcome,
  reason,
  pressureState: approver.pressureState,
  agentReasoning: proposal.reason,
})

export function runProposalCycle(
  approver: Approver,
  requestClasses: RequestClass[],
  recentLedger: LedgerEntry[],
  now: number,
  backupApprover?: BackupContext,
): LedgerEntry[] {
  const entries: LedgerEntry[] = []
  const proposals = runGovernanceAgent(approver, requestClasses, now, backupApprover)

  for (const proposal of proposals) {
    const request = approver.queue.find((item) => item.requestId === proposal.requestId)
    const requestClass = request && requestClasses.find((item) => item.name === request.className)
    if (!request || !requestClass) continue

    const validation = validateProposal(proposal, request, requestClass, approver, [...recentLedger, ...entries], now)
    if (validation.ok) {
      const outcome = outcomeFor(proposal.kind)
      if (outcome) {
        const reason = proposal.kind === 'escalate_to_human'
          ? `Escalation noted; human review required. ${validation.reason}`
          : validation.reason
        entries.push(commit(proposal, outcome, approver, now, reason))
      }
      continue
    }

    entries.push(commit(
      proposal,
      'rejected_proposal',
      approver,
      now,
      `Agent proposed ${proposalLabel(proposal)}; policy rejected it: ${validation.reason}`,
    ))

    const retry = retryRejectedProposal(proposal, validation.reason)
    if (!retry) continue

    const retryValidation = validateProposal(retry, request, requestClass, approver, [...recentLedger, ...entries], now)
    if (retryValidation.ok) {
      const outcome = outcomeFor(retry.kind)
      if (outcome) entries.push(commit(retry, outcome, approver, now, retryValidation.reason))
    } else {
      entries.push(commit(
        retry,
        'rejected_proposal',
        approver,
        now,
        `Fallback proposal ${proposalLabel(retry)} was also rejected: ${retryValidation.reason}`,
      ))
    }
  }

  return entries
}
