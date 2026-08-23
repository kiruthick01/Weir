import type { DecisionOutcome, LedgerEntry } from '@/lib/types'

const accentOutcomes: DecisionOutcome[] = ['timed_out', 'rejected_proposal']

export function DecisionLedger({ entries }: { entries: LedgerEntry[] }) {
  return (
    <div className="border-2 border-ink">
      <div className="flex items-center justify-between border-b-2 border-ink px-4 py-3">
        <h3 className="text-sm font-bold uppercase tracking-wide">Decision ledger</h3>
        <span className="font-mono text-xs text-muted">append-only · {entries.length} events</span>
      </div>
      <div className="max-h-[360px] overflow-y-auto">
        {entries.length === 0 ? (
          <p className="py-12 text-center text-sm italic text-muted">Waiting for the first decision event…</p>
        ) : (
          <table className="w-full border-collapse text-left">
            <tbody>
              {[...entries].reverse().map((entry) => (
                <LedgerRow key={entry.id} entry={entry} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function LedgerRow({ entry }: { entry: LedgerEntry }) {
  return (
    <tr className="animate-row-enter border-b border-line align-top">
      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted">{new Date(entry.timestamp).toLocaleTimeString()}</td>
      <td className={`whitespace-nowrap px-4 py-2 font-mono text-xs font-bold lowercase ${accentOutcomes.includes(entry.outcome) ? 'text-accent' : ''}`}>{entry.outcome}</td>
      <td className="px-4 py-2 text-sm">
        {entry.reason}
        {entry.agentReasoning && <details className="mt-1"><summary className="cursor-pointer font-mono text-[11px] uppercase tracking-wide text-muted">agent reasoning</summary><p className="mt-1 font-mono text-xs leading-5 text-muted">{entry.agentReasoning}</p></details>}
      </td>
    </tr>
  )
}
