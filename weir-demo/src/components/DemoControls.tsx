import { useEffect, useRef, useState, type Dispatch } from 'react'
import type { RequestClass } from '@/lib/types'
import type { WeirAction } from '@/state/weirReducer'

const makeAmount = (requestClass: RequestClass) => {
  if (requestClass.autoApproveThreshold === null) return Math.round(1500 + Math.random() * 8500)
  const belowThreshold = Math.random() < 0.5
  return belowThreshold
    ? Math.max(50, Math.round(requestClass.autoApproveThreshold * (0.25 + Math.random() * 0.55)))
    : Math.round(requestClass.autoApproveThreshold * (1.35 + Math.random() * 2.2))
}

export function DemoControls({ selectedApproverId, requestClasses, dispatch, onReset }: { selectedApproverId: string; requestClasses: RequestClass[]; dispatch: Dispatch<WeirAction>; onReset: () => void }) {
  const [ramping, setRamping] = useState(false)
  const rampTimerRef = useRef<number | null>(null)
  const stepRef = useRef(0)

  const stopRamp = () => {
    if (rampTimerRef.current !== null) {
      window.clearInterval(rampTimerRef.current)
      rampTimerRef.current = null
    }
    stepRef.current = 0
    setRamping(false)
  }

  useEffect(() => stopRamp, [])

  const startRamp = () => {
    if (ramping || rampTimerRef.current !== null || requestClasses.length === 0) return
    setRamping(true)
    stepRef.current = 0
    rampTimerRef.current = window.setInterval(() => {
      const step = stepRef.current++
      const requestClass = requestClasses[step % requestClasses.length]
      const now = Date.now()

      dispatch({ type: 'ENQUEUE_REQUEST', approverId: selectedApproverId, className: requestClass.name, amount: makeAmount(requestClass), now })

      if (step > 0 && step % 5 === 0) {
        dispatch({ type: 'RECORD_LATENCY_SAMPLE', approverId: selectedApproverId, latencyMs: 7_500 + step * 1_250 })
      }

      if (step >= 49) stopRamp()
    }, 400)
  }

  const reset = () => {
    stopRamp()
    dispatch({ type: 'RESET' })
    onReset()
  }

  const forceCritical = () => {
    if (!selectedApproverId) return
    dispatch({ type: 'FORCE_CRITICAL', approverId: selectedApproverId })
  }

  const buttonClass = 'border border-ink px-3 py-1.5 font-mono text-xs uppercase tracking-wide disabled:opacity-40 hover:bg-ink hover:text-paper disabled:hover:bg-transparent disabled:hover:text-ink'

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={startRamp} disabled={ramping} className={`${buttonClass} bg-ink text-paper hover:bg-ink`}>
        {ramping ? 'Ramping…' : 'Ramp load'}
      </button>
      <button type="button" disabled={!selectedApproverId} onClick={() => dispatch({ type: 'RUN_AGENT_CYCLE', approverId: selectedApproverId })} className={buttonClass}>
        Trigger agent cycle
      </button>
      <button type="button" disabled={!selectedApproverId} onClick={forceCritical} className={`${buttonClass} border-accent text-accent hover:bg-accent hover:text-paper`}>
        Force critical
      </button>
      <button type="button" onClick={reset} className={`${buttonClass} border-line text-muted hover:bg-ink hover:text-paper`}>
        Reset demo
      </button>
      {ramping && <span className="font-mono text-xs uppercase tracking-wide text-muted">synthetic load active</span>}
    </div>
  )
}
