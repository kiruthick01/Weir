import { Badge } from '@/components/ui/badge'

export function Legend() {
  return <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-zinc-500"><span className="font-semibold uppercase tracking-widest text-zinc-400">Legend</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-emerald-400" /> Normal</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-amber-400" /> Elevated</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-red-400" /> Critical</span><Badge className="border-slate-500/30 bg-slate-500/15 text-slate-300">queued</Badge><Badge className="border-blue-500/30 bg-blue-500/15 text-blue-300">delegated</Badge><Badge className="border-emerald-500/30 bg-emerald-500/15 text-emerald-300">auto-approved</Badge><Badge className="border-orange-500/50 bg-orange-500/10 text-orange-300">rejected proposal</Badge></div>
}
