import { useEffect, useRef, useState } from 'react'
import { Activity, CircleCheck, Clock3, Inbox, OctagonAlert, TriangleAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { computeP50 } from '@/lib/engine'
import type { Approver } from '@/lib/types'
import { cn } from '@/lib/utils'

const pressureStyles = {
  normal: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300',
  elevated: 'border-amber-500/40 bg-amber-500/15 text-amber-300',
  critical: 'border-red-500/40 bg-red-500/15 text-red-300',
}

const pressureIcons = {
  normal: CircleCheck,
  elevated: TriangleAlert,
  critical: OctagonAlert,
}

export function ApproverCard({ approver, selected, onSelect }: { approver: Approver; selected: boolean; onSelect: () => void }) {
  const p50 = computeP50(approver.latencyWindow)
  const criticalSeconds = Math.max(0, Math.floor((Date.now() - approver.stateSince) / 1000))
  const previousPressure = useRef(approver.pressureState)
  const [pressureChanged, setPressureChanged] = useState(false)
  const PressureIcon = pressureIcons[approver.pressureState]

  useEffect(() => {
    if (previousPressure.current !== approver.pressureState) {
      previousPressure.current = approver.pressureState
      setPressureChanged(true)
      const timeout = window.setTimeout(() => setPressureChanged(false), 850)
      return () => window.clearTimeout(timeout)
    }
  }, [approver.pressureState])

  return (
    <button type="button" onClick={onSelect} className="block w-full text-left">
      <Card className={cn('h-full border-zinc-800 bg-zinc-900/80 transition-all duration-300 hover:border-zinc-600', selected && 'border-cyan-400/80 ring-2 ring-cyan-400/30', pressureChanged && 'animate-pressure-flash')}>
        <CardHeader className="gap-3 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle className="text-base text-zinc-100">{approver.name}</CardTitle>
              <p className="mt-1 font-mono text-[11px] text-zinc-500">{approver.id}</p>
            </div>
            <Badge className={cn('border transition-colors duration-300', pressureStyles[approver.pressureState])}>
              <PressureIcon className="size-3.5" aria-hidden="true" />
              {approver.pressureState}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 pt-0">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3"><div className="flex items-center gap-2 text-xs text-zinc-500"><Inbox className="size-3.5" /> Queue</div><div className="mt-1 font-mono text-xl text-zinc-100">{approver.queue.length}</div></div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3"><div className="flex items-center gap-2 text-xs text-zinc-500"><Activity className="size-3.5" /> p50 latency</div><div className="mt-1 font-mono text-xl text-zinc-100">{(p50 / 1000).toFixed(1)}s</div></div>
          <div className="col-span-2 flex items-center gap-2 font-mono text-xs text-zinc-500"><Clock3 className="size-3.5" />{approver.pressureState === 'critical' ? `critical for ${criticalSeconds}s` : `state since ${new Date(approver.stateSince).toLocaleTimeString()}`}</div>
        </CardContent>
      </Card>
    </button>
  )
}
