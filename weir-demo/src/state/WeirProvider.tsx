import { createContext, useEffect, useMemo, useReducer, useRef, type Dispatch, type ReactNode } from 'react'
import { createSeedState } from '../lib/seed'
import { weirReducer, type WeirAction } from './weirReducer'
import type { WeirState } from '../lib/types'

export const WeirContext = createContext<{ state: WeirState; dispatch: Dispatch<WeirAction> } | null>(null)

export function WeirProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(weirReducer, undefined, createSeedState)
  const previousPressureRef = useRef(new Map<string, string>())
  const lastAgentRunRef = useRef(new Map<string, number>())

  useEffect(() => {
    const timer = window.setInterval(() => dispatch({ type: 'TICK' }), 250)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const now = Date.now()

    for (const approver of state.approvers) {
      const previous = previousPressureRef.current.get(approver.id) ?? approver.pressureState
      const lastRun = lastAgentRunRef.current.get(approver.id) ?? 0
      const pressureNeedsAgent = approver.pressureState === 'elevated' || approver.pressureState === 'critical'
      const enteredPressureState = previous !== approver.pressureState && pressureNeedsAgent
      // Five seconds keeps the local demo responsive; a production scheduler
      // should use the architecture's 30–60 second sustained-pressure cadence.
      const needsPeriodicRun = pressureNeedsAgent && now - lastRun >= 5_000

      if (enteredPressureState || needsPeriodicRun) {
        dispatch({ type: 'RUN_AGENT_CYCLE', approverId: approver.id, now })
        lastAgentRunRef.current.set(approver.id, now)
      }

      previousPressureRef.current.set(approver.id, approver.pressureState)
    }
  }, [state])

  const value = useMemo(() => ({ state, dispatch }), [state])
  return <WeirContext.Provider value={value}>{children}</WeirContext.Provider>
}
