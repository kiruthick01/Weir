import { computeDeadlines, enqueueRequest, evaluatePressure } from '../lib/engine'
import { createSeedState } from '../lib/seed'
import type { WeirState } from '../lib/types'

export type WeirAction =
  | { type: 'ENQUEUE_REQUEST'; approverId: string; className: string; amount: number; now?: number }
  | { type: 'TICK'; now?: number }
  | { type: 'RESET' }

const id = () => `ledger-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

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
  } else {
    for (const approver of approvers) {
      evaluatePressure(approver, now)
      const timedOutIds = new Set(computeDeadlines(approver, now).filter((item) => item.timedOut).map((item) => item.requestId))
      for (const request of approver.queue) {
        if (timedOutIds.has(request.requestId)) {
          ledger.push({ id: id(), timestamp: now, approverId: approver.id, requestId: request.requestId, outcome: 'timed_out', reason: 'Bounded max-wait deadline expired.', pressureState: approver.pressureState })
        }
      }
      approver.queue = approver.queue.filter((request) => !timedOutIds.has(request.requestId))
    }
  }
  return { ...state, approvers, ledger }
}
