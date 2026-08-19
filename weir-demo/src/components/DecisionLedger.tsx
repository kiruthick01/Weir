import { CheckCircle2, ChevronDown, CircleAlert, CircleDashed, Clock4, GitBranch, ScrollText, UserCheck } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { DecisionOutcome, LedgerEntry } from '@/lib/types'
import { cn } from '@/lib/utils'

const outcomeStyles: Record<DecisionOutcome, string> = { queued: 'bg-slate-500/15 text-slate-300 border-slate-500/30', delegated: 'bg-blue-500/15 text-blue-300 border-blue-500/30', auto_approved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', manually_approved: 'bg-teal-500/15 text-teal-300 border-teal-500/30', timed_out: 'bg-red-500/15 text-red-300 border-red-500/30', rejected_proposal: 'bg-orange-500/10 text-orange-300 border-orange-500/50' }
const outcomeIcons: Record<DecisionOutcome, typeof CheckCircle2> = { queued: CircleDashed, delegated: GitBranch, auto_approved: CheckCircle2, manually_approved: UserCheck, timed_out: Clock4, rejected_proposal: CircleAlert }

export function DecisionLedger({ entries }: { entries: LedgerEntry[] }) {
  return <Card className="border-zinc-800 bg-zinc-900/80"><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><ScrollText className="size-5 text-cyan-300" /> Decision ledger <span className="font-mono text-sm font-normal text-zinc-500">append-only · {entries.length} events</span></CardTitle></CardHeader><CardContent><ScrollArea className="h-[360px] pr-4"><div className="space-y-2">{entries.length === 0 ? <p className="py-12 text-center text-sm text-zinc-500">Waiting for the first decision event…</p> : [...entries].reverse().map((entry) => <LedgerRow key={entry.id} entry={entry} />)}</div></ScrollArea></CardContent></Card>
}

function LedgerRow({ entry }: { entry: LedgerEntry }) {
  const [open, setOpen] = useState(false)
  const OutcomeIcon = outcomeIcons[entry.outcome]

  return <div className="animate-ledger-enter rounded-lg border border-zinc-800 bg-zinc-950/50 p-3"><div className="flex flex-wrap items-start gap-3"><span className="min-w-24 font-mono text-xs text-zinc-500">{new Date(entry.timestamp).toLocaleTimeString()}</span><Badge className={cn('border', outcomeStyles[entry.outcome])}><OutcomeIcon className="size-3.5" aria-hidden="true" />{entry.outcome}</Badge><span className="min-w-0 flex-1 text-sm leading-5 text-zinc-300">{entry.reason}</span></div>{entry.agentReasoning && <Collapsible open={open} onOpenChange={setOpen} className="mt-2 border-t border-zinc-800 pt-2"><CollapsibleTrigger className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"><ChevronDown className={cn('size-3 transition-transform', open && 'rotate-180')} /> Agent reasoning</CollapsibleTrigger><CollapsibleContent className="pt-2 font-mono text-xs leading-5 text-zinc-500">{entry.agentReasoning}</CollapsibleContent></Collapsible>}</div>
}
