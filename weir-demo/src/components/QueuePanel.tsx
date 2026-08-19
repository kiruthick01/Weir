import { Clock3, ListTodo } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { computeDeadlines } from '@/lib/engine'
import type { Approver, RequestClass } from '@/lib/types'
import { cn } from '@/lib/utils'

const formatCountdown = (milliseconds: number) => {
  const seconds = Math.ceil(milliseconds / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function QueuePanel({ approver, requestClasses, now }: { approver: Approver; requestClasses: RequestClass[]; now: number }) {
  const deadlines = computeDeadlines(approver, now)

  return (
    <Card className="border-zinc-800 bg-zinc-900/80">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg"><ListTodo className="size-5 text-cyan-300" /> Bounded queue</CardTitle>
          <p className="mt-1 text-sm text-zinc-500">Requests admitted to {approver.name}</p>
        </div>
        <Badge variant="outline" className="font-mono text-zinc-300">{approver.queue.length} waiting</Badge>
      </CardHeader>
      <CardContent>
        {approver.queue.length === 0 ? (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed border-zinc-800 text-sm text-zinc-500">No requests in queue</div>
        ) : (
          <Table>
            <TableHeader><TableRow className="border-zinc-800 hover:bg-transparent"><TableHead>Request</TableHead><TableHead>Class</TableHead><TableHead>Amount</TableHead><TableHead className="text-right">Deadline</TableHead></TableRow></TableHeader>
            <TableBody>
              {approver.queue.map((request) => {
                const deadline = deadlines.find((item) => item.requestId === request.requestId)
                const requestClass = requestClasses.find((item) => item.name === request.className)
                const remaining = deadline?.msRemaining ?? 0
                const ratio = requestClass ? remaining / (requestClass.maxWaitSeconds * 1000) : 1
                const warm = deadline?.timedOut ? 'bg-red-950/50' : ratio < 0.2 ? 'bg-red-950/30' : ratio < 0.5 ? 'bg-amber-950/25' : ''
                return (
                  <TableRow key={request.requestId} className={cn('border-zinc-800 transition-colors duration-300', warm)}>
                    <TableCell className="max-w-28 truncate font-mono text-xs text-zinc-300">{request.requestId}</TableCell>
                    <TableCell className="text-xs text-zinc-400">{request.className}</TableCell>
                    <TableCell className="font-mono text-sm text-zinc-200">${request.amount.toLocaleString()}</TableCell>
                    <TableCell className="text-right">
                      {deadline?.timedOut ? <Badge variant="destructive">TIMED OUT</Badge> : <span className="inline-flex items-center gap-1 font-mono text-sm text-zinc-300"><Clock3 className="size-3.5" />{formatCountdown(remaining)}</span>}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
