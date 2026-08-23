import { computeP50 } from '@/lib/engine'
import type { Approver } from '@/lib/types'

const fill = { normal: 0.33, elevated: 0.66, critical: 1 }

export function ApproverCard({ approver, selected, onSelect }: { approver: Approver; selected: boolean; onSelect: () => void }) {
  const p50 = computeP50(approver.latencyWindow)
  const criticalSeconds = Math.max(0, Math.floor((Date.now() - approver.stateSince) / 1000))

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`block w-full border p-4 text-left transition-colors ${selected ? 'border-ink bg-tint shadow-[inset_4px_0_0_var(--color-accent)]' : 'border-line hover:bg-tint'}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold">{approver.name}</div>
          <div className="mt-0.5 font-mono text-[11px] text-muted">{approver.id}</div>
        </div>
        <span className={`font-mono text-xs font-bold lowercase ${approver.pressureState === 'critical' ? 'text-accent' : ''}`}>{approver.pressureState}</span>
      </div>

      <div className="mt-3 h-2.5 bg-tint">
        <div
          className={`h-full ${approver.pressureState === 'critical' ? 'bg-accent' : approver.pressureState === 'elevated' ? 'bg-muted' : 'bg-ink'}`}
          style={{ width: `${Math.round(fill[approver.pressureState] * 100)}%` }}
        />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 border-t border-line pt-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wide text-muted">Queue</div>
          <div className="font-mono text-lg font-bold">{approver.queue.length}</div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wide text-muted">p50 latency</div>
          <div className="font-mono text-lg font-bold">{(p50 / 1000).toFixed(1)}s</div>
        </div>
      </div>

      <div className="mt-2 font-mono text-[11px] text-muted">
        {approver.pressureState === 'critical' ? `critical for ${criticalSeconds}s` : `state since ${new Date(approver.stateSince).toLocaleTimeString()}`}
      </div>
    </button>
  )
}
