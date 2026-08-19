export type PressureState = 'normal' | 'elevated' | 'critical'
export type RiskTier = 'low' | 'medium' | 'high'
export type DecisionOutcome =
  | 'queued' | 'delegated' | 'auto_approved' | 'manually_approved'
  | 'timed_out' | 'rejected_proposal'
export type ProposalKind = 'delegate' | 'auto_approve' | 'escalate_to_human' | 'hold'

export interface RequestClass {
  name: string
  maxWaitSeconds: number
  autoApproveThreshold: number | null
  riskTier: RiskTier
}

export interface QueuedRequest {
  requestId: string
  className: string
  amount: number
  enqueuedAt: number
  deadline: number
}

export interface Approver {
  id: string
  name: string
  pressureState: PressureState
  stateSince: number
  backupApproverId: string
  latencyWindow: number[]
  queue: QueuedRequest[]
}

export interface Proposal {
  requestId: string
  kind: ProposalKind
  targetApproverId?: string
  reason: string
}

export interface LedgerEntry {
  id: string
  timestamp: number
  approverId: string
  requestId: string
  outcome: DecisionOutcome
  reason: string
  pressureState: PressureState
  agentReasoning?: string
}

export interface WeirState {
  approvers: Approver[]
  requestClasses: RequestClass[]
  ledger: LedgerEntry[]
}
