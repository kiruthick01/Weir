import { computeDeadlines, enqueueRequest, evaluatePressure } from '../lib/engine'
import { hasTerminalDecision, isTerminalEntry, runProposalCycle } from '../lib/agent'
import { createSeedState } from '../lib/seed'
import { recordDecisionLatency } from '../lib/engine'
import type { LedgerEntry, WeirState } from '../lib/types'

export type WeirAction =
  | { type: 'ENQUEUE_REQUEST'; approverId: string; className: string; amount: number; now?: number }
  | { type: 'TICK'; now?: number }
  | { type: 'RECORD_LATENCY_SAMPLE'; approverId: string; latencyMs: number; now?: number }
  | { type: 'RUN_AGENT_CYCLE'; approverId: string; now?: number }
  | { type: 'RESET' }

const id = () => `ledger-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

const terminalRequestIds = (entries: LedgerEntry[]) =>
  new Set(entries.filter(isTerminalEntry).map((entry) => entry.requestId))

export function weirReducer(state: WeirState, action: WeirAction): WeirState {
  if (action.type === 'RESET') return createSeedState()
  const now = action.now ?? Date.now()
  const approvers = state.approvers.map((approver) => ({ ...approver, latencyWindow: [...approver.latencyWindow], queue: [...approver.queue] }))
  const ledger = [...state.ledger]

  if (action.type === 'ENQUEUE_REQUEST') {
    const approver = approvers.find((item) => item.id === action.approverId)
    const requestClass = state.requestClasses.find((item) => item.name === action.className)
    if (!approver || !requestClass) return state
    const request = enqueueRequest(approver, requestClass, action.amount, now)
    ledger.push({ id: id(), timestamp: now, approverId: approver.id, requestId: request.requestId, outcome: 'queued', reason: 'Request admitted to bounded approver queue.', pressureState: approver.pressureState })
  } else if (action.type === 'RUN_AGENT_CYCLE') {
    const approver = approvers.find((item) => item.id === action.approverId)
    if (!approver) return state
    const backupApprover = approvers.find((item) => item.id === approver.backupApproverId)
    const newEntries = runProposalCycle(approver, state.requestClasses, ledger, now, backupApprover)
    const completedIds = terminalRequestIds(newEntries)
    approver.queue = approver.queue.filter((request) => !completedIds.has(request.requestId))
    return { ...state, approvers, ledger: [...ledger, ...newEntries] }
  } else if (action.type === 'RECORD_LATENCY_SAMPLE') {
    const approver = approvers.find((item) => item.id === action.approverId)
    if (!approver) return state
    recordDecisionLatency(approver, action.latencyMs)
  } else {
    for (const approver of approvers) {
      evaluatePressure(approver, now)
      const terminalIds = terminalRequestIds(ledger)
      const timedOutIds = new Set(computeDeadlines(approver, now)
        .filter((item) => item.timedOut && !terminalIds.has(item.requestId))
        .map((item) => item.requestId))
      for (const request of approver.queue) {
        // Defensive guard: queue membership is not the source of truth for
        // terminality; the ledger is. This prevents duplicate timeout events
        // even if a stale queue snapshot is ever supplied.
        if (timedOutIds.has(request.requestId) && !hasTerminalDecision(ledger, request.requestId)) {
          ledger.push({ id: id(), timestamp: now, approverId: approver.id, requestId: request.requestId, outcome: 'timed_out', reason: 'Bounded max-wait deadline expired.', pressureState: approver.pressureState })
        }
      }
      // timedOutIds already excludes requests with terminal ledger entries;
      // every remaining timed-out request is removed in this same update.
      approver.queue = approver.queue.filter((request) => !timedOutIds.has(request.requestId))
    }
  }
  return { ...state, approvers, ledger }
}
