export interface ExecutionCounts {
  pending: number;
  approved: number;
  submitted: number;
  filled: number;
  rejectedFailed: number;
  queueRejectedBroker: number;
  reconciledTotal: number;
}

export interface ExecutionBrokerState {
  name: string;
  status: string;
}

export interface ExecutionOrderRow {
  id: string;
  lifecycle: string;
  status: string;
  engine?: string;
  ticker?: string;
  side?: string;
  quantity?: number | null;
  broker?: string;
  brokerOrderId?: string;
  requestId?: string;
  timestamp?: string;
  message?: string;
}

export interface ExecutionSnapshot {
  counts: ExecutionCounts;
  brokerState: ExecutionBrokerState[];
  pending: ExecutionOrderRow[];
  approved: ExecutionOrderRow[];
  submitted: ExecutionOrderRow[];
  filled: ExecutionOrderRow[];
  rejectedFailed: ExecutionOrderRow[];
}

export type ExecutionLifecycleFilter =
  | 'all'
  | 'pending'
  | 'approved'
  | 'submitted'
  | 'filled'
  | 'rejected_failed';

export interface ExecutionSyncSummary {
  totalChecked: number;
  filled: number;
  pending: number;
  rejected: number;
  failed: number;
  exitsChecked?: number;
  exitsClosed?: number;
  errors: string[];
}

export interface ExecutionActionResult {
  success: boolean;
  kind: string;
  message: string;
  outcome?: string;
  requestId?: string;
  brokerOrderId?: string;
  sync?: ExecutionSyncSummary;
}
