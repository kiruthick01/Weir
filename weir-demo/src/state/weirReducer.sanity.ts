import { isTerminalEntry } from '../lib/agent'
import type { LedgerEntry, WeirState } from '../lib/types'

/**
 * Invariant used by the ramp demo: every request can receive at most one
 * terminal decision, and terminal decisions cannot outnumber enqueued work.
 */
export function assertTerminalDecisionInvariant(state: WeirState): void {
  const enqueuedIds = new Set(state.ledger.filter((entry) => entry.outcome === 'queued').map((entry) => entry.requestId))
  const terminalEntries = state.ledger.filter((entry) => isTerminalEntry(entry) && entry.outcome !== 'queued')
  const terminalCounts = new Map<string, number>()

  for (const entry of terminalEntries) {
    terminalCounts.set(entry.requestId, (terminalCounts.get(entry.requestId) ?? 0) + 1)
  }

  if ([...terminalCounts.values()].some((count) => count > 1)) {
    throw new Error('Weir invariant failed: a request has more than one terminal decision')
  }
  if (terminalEntries.some((entry) => !enqueuedIds.has(entry.requestId))) {
    throw new Error('Weir invariant failed: terminal decision has no enqueued request')
  }
  if (terminalEntries.length > enqueuedIds.size) {
    throw new Error('Weir invariant failed: terminal decisions exceed enqueued requests')
  }
}

export function terminalDecisionCounts(ledger: LedgerEntry[]) {
  return ledger.reduce<Record<string, number>>((counts, entry) => {
    if (isTerminalEntry(entry) && entry.outcome !== 'queued') {
      counts[entry.requestId] = (counts[entry.requestId] ?? 0) + 1
    }
    return counts
  }, {})
}
