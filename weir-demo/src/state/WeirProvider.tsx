import { createContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import { createSeedState } from '../lib/seed'
import { weirReducer, type WeirAction } from './weirReducer'
import type { WeirState } from '../lib/types'

export const WeirContext = createContext<{ state: WeirState; dispatch: Dispatch<WeirAction> } | null>(null)

export function WeirProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(weirReducer, undefined, createSeedState)
  useEffect(() => {
    const timer = window.setInterval(() => dispatch({ type: 'TICK' }), 250)
    return () => window.clearInterval(timer)
  }, [])
  const value = useMemo(() => ({ state, dispatch }), [state])
  return <WeirContext.Provider value={value}>{children}</WeirContext.Provider>
}
