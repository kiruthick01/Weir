import type { Approver, RequestClass, WeirState } from './types'

export const createSeedState = (): WeirState => {
  const now = Date.now()
  const approvers: Approver[] = [
    { id: 'approver-1', name: 'Maya Chen', pressureState: 'normal', stateSince: now, backupApproverId: 'approver-2', latencyWindow: [3500, 4200, 5100, 3900], queue: [] },
    { id: 'approver-2', name: 'Jon Bell', pressureState: 'normal', stateSince: now, backupApproverId: 'approver-1', latencyWindow: [2800, 3600, 4100, 3300], queue: [] },
    { id: 'approver-3', name: 'Priya Shah', pressureState: 'normal', stateSince: now, backupApproverId: 'approver-4', latencyWindow: [6200, 7100, 5800, 6600], queue: [] },
    { id: 'approver-4', name: 'Owen Wright', pressureState: 'normal', stateSince: now, backupApproverId: 'approver-3', latencyWindow: [4400, 5200, 4800, 5600], queue: [] },
  ]
  const requestClasses: RequestClass[] = [
    { name: 'procurement_low_value', maxWaitSeconds: 60, autoApproveThreshold: 1000, riskTier: 'low' },
    { name: 'procurement_high_value', maxWaitSeconds: 180, autoApproveThreshold: null, riskTier: 'high' },
    { name: 'access_request_standard', maxWaitSeconds: 90, autoApproveThreshold: null, riskTier: 'medium' },
  ]
  return { approvers, requestClasses, ledger: [] }
}
