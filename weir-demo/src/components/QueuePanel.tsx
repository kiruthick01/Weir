import { computeDeadlines } from '@/lib/engine'
import type { Approver } from '@/lib/types'

const formatCountdown = (milliseconds: number) => {
  const seconds = Math.ceil(milliseconds / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function QueuePanel({ approver, now }: { approver: Approver; now: number }) {
  const deadlines = computeDeadlines(approver, now)

  return (
    <div className="border-2 border-ink">
      <div className="flex items-center justify-between border-b-2 border-ink px-4 py-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wide">Bounded queue</h3>
          <p className="mt-0.5 text-xs text-muted">Requests admitted to {approver.name}</p>
        </div>
        <span className="font-mono text-xs text-muted">{approver.queue.length} waiting</span>
      </div>

      {approver.queue.length === 0 ? (
        <div className="flex min-h-40 items-center justify-center text-sm italic text-muted">No requests in queue</div>
      ) : (
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b-2 border-ink">
              <th className="px-4 py-2 font-mono text-[10px] uppercase tracking-wide text-muted">Request</th>
              <th className="px-4 py-2 font-mono text-[10px] uppercase tracking-wide text-muted">Class</th>
              <th className="px-4 py-2 font-mono text-[10px] uppercase tracking-wide text-muted">Amount</th>
              <th className="px-4 py-2 text-right font-mono text-[10px] uppercase tracking-wide text-muted">Deadline</th>
            </tr>
          </thead>
          <tbody>
            {approver.queue.map((request) => {
              const deadline = deadlines.find((item) => item.requestId === request.requestId)
              const remaining = deadline?.msRemaining ?? 0
              return (
                <tr key={request.requestId} className={`border-b border-line ${deadline?.timedOut ? 'bg-accent/5' : ''}`}>
                  <td className="max-w-28 truncate px-4 py-2 font-mono text-xs">{request.requestId}</td>
                  <td className="px-4 py-2 font-mono text-xs text-muted">{request.className}</td>
                  <td className="px-4 py-2 font-mono text-sm">${request.amount.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right font-mono text-sm">
                    {deadline?.timedOut ? <span className="font-bold text-accent">TIMED OUT</span> : formatCountdown(remaining)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
