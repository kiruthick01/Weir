import { useEffect, useRef, useState, type Dispatch } from 'react'
import { Bot, Play, RotateCcw, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
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

  const agentCycleDisabled = !selectedApproverId
  console.debug('[DemoControls] Trigger Agent Cycle disabled:', agentCycleDisabled, { selectedApproverId })

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={startRamp} disabled={ramping} className="bg-cyan-500 text-zinc-950 hover:bg-cyan-400">
        <Play className="size-4" />
        {ramping ? 'Ramping…' : 'Ramp Load'}
      </Button>
      <Button variant="outline" disabled={!selectedApproverId} onClick={() => dispatch({ type: 'RUN_AGENT_CYCLE', approverId: selectedApproverId })}>
        <Bot className="size-4" />
        Trigger Agent Cycle
      </Button>
      <Button variant="ghost" onClick={reset} className="text-zinc-400 hover:text-zinc-100">
        <RotateCcw className="size-4" />
        Reset Demo
      </Button>
      {ramping && <span className="flex items-center gap-1.5 font-mono text-xs text-cyan-300"><Zap className="size-3.5 animate-pulse" /> synthetic load active</span>}
    </div>
  )
}
