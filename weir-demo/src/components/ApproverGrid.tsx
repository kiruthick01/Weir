import type { Approver } from '@/lib/types'
import { ApproverCard } from './ApproverCard'

export function ApproverGrid({
  approvers,
  selectedApproverId,
  onSelect,
}: {
  approvers: Approver[]
  selectedApproverId: string
  onSelect: (approverId: string) => void
}) {
  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {approvers.map((approver) => (
        <ApproverCard
          key={approver.id}
          approver={approver}
          selected={approver.id === selectedApproverId}
          onSelect={() => onSelect(approver.id)}
        />
      ))}
    </section>
  )
}
