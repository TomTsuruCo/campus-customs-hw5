export type Role = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  /** exact stored workflow state */
  status: 'open' | 'in_progress' | 'blocked' | 'awaiting_human_approval' | 'resolved'
  created_at: string
  /** the backend's simple view: open or resolved */
  state: 'open' | 'resolved'
}

export interface Balance {
  account: string
  balance: number
  as_of: string
}

export interface AgentEvent {
  event_id: string
  timestamp_utc: string
  run_id?: string
  ticket_id?: number
  kind: string
  agent?: string
  from_agent?: string
  tool_name?: string
  tool_arguments?: Record<string, unknown>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tool_output?: any
  said?: string
  findings?: string[]
  recommendation?: string
  recommended_status?: string
  human_action_required?: boolean
  resolution?: string
  resolved_by?: string
  usage?: { requests?: number; tool_calls?: number; total_tokens?: number }
  error?: string
}

export interface RunResult {
  run_id: string
  tickets: { ticket_id: number; agents_used: Role[] }[]
}

export interface ApprovalResult {
  payment_made: boolean
  payment_id?: number
  amount: number
  balance: number
  kind?: string
  ticket_status?: string
}
