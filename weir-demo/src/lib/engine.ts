import type { Approver, PressureState, QueuedRequest, RequestClass } from './types'

const ELEVATED_P50 = 10_000
const CRITICAL_P50 = 20_000
const HYSTERESIS = 0.75
const STATE_COOLDOWN_MS = 8_000
const WINDOW_SIZE = 30

export const computeP50 = (values: number[]) => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

const rawPressure = (p50: number): PressureState =>
  p50 >= CRITICAL_P50 ? 'critical' : p50 >= ELEVATED_P50 ? 'elevated' : 'normal'

export function evaluatePressure(approver: Approver, now: number): { state: PressureState; changed: boolean } {
  const current = approver.pressureState
  const p50 = computeP50(approver.latencyWindow)
  const candidate = rawPressure(p50)
  if (now - approver.stateSince < STATE_COOLDOWN_MS) return { state: current, changed: false }

  let next = current
  if (current === 'normal' && candidate !== 'normal') next = 'elevated'
  else if (current === 'elevated') {
    if (p50 >= CRITICAL_P50) next = 'critical'
    else if (p50 <= ELEVATED_P50 * HYSTERESIS) next = 'normal'
  } else if (current === 'critical') {
    if (p50 <= CRITICAL_P50 * HYSTERESIS) next = 'elevated'
  }

  if (next !== current) {
    approver.pressureState = next
    approver.stateSince = now
  }
  return { state: next, changed: next !== current }
}

export function enqueueRequest(approver: Approver, requestClass: RequestClass, amount: number, now: number): QueuedRequest {
  const request: QueuedRequest = {
    requestId: `req-${now}-${Math.random().toString(36).slice(2, 8)}`,
    className: requestClass.name,
    amount,
    enqueuedAt: now,
    deadline: now + requestClass.maxWaitSeconds * 1000,
  }
  approver.queue.push(request)
  return request
}

export function computeDeadlines(approver: Approver, now: number) {
  return approver.queue.map(({ requestId, deadline }) => ({
    requestId,
    msRemaining: Math.max(0, deadline - now),
    timedOut: now >= deadline,
  }))
}

export function recordDecisionLatency(approver: Approver, latencyMs: number): void {
  approver.latencyWindow = [...approver.latencyWindow, Math.max(0, latencyMs)].slice(-WINDOW_SIZE)
}
