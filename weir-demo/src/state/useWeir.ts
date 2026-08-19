import { useContext } from 'react'
import { WeirContext } from './WeirProvider'

export function useWeir() {
  const context = useContext(WeirContext)
  if (!context) throw new Error('useWeir must be used inside a WeirProvider')
  return context
}
