import type { AgentEvent, Role, Ticket } from './types'

export const ROLES: Role[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const PERSONAS: Record<Role, { name: string; tag: string; emoji: string; color: string }> = {
  boss: { name: 'Boss', tag: 'Runs the desk', emoji: '🧭', color: '#c9a24b' },
  inventory: { name: 'Inventory', tag: 'Counts the stock', emoji: '📦', color: '#d9822b' },
  accounting: { name: 'Accounting', tag: 'Watches the money', emoji: '🧾', color: '#3f9a73' },
  facilities: { name: 'Facilities', tag: 'Rent, lease & premises', emoji: '🔑', color: '#5f86a8' },
  customer_service: { name: 'Customer Service', tag: 'Drafts replies, never sends', emoji: '💬', color: '#cf6384' },
}

export const STATUS_LABEL: Record<Ticket['status'], string> = {
  open: 'On the desk',
  in_progress: 'In progress',
  blocked: 'Blocked',
  awaiting_human_approval: 'Needs your OK',
  resolved: 'Resolved',
}

const TOOL_LABEL: Record<string, string> = {
  list_open_tickets: 'checking the inbox',
  get_ticket_details: 'opening the ticket file',
  check_inventory: 'counting stock',
  get_shop_financial_status: 'reading the books',
  list_vendors_with_shipping_status: 'checking vendor shipping',
  append_ticket_note: 'writing a ticket note',
  save_customer_draft: 'drafting a reply (unsent)',
  request_payment_approval: 'asking for your OK on a payment',
  update_ticket_status: 'updating the ticket status',
  approve_payment: 'paying out of checking',
}
export const toolLabel = (name?: string) => (name && TOOL_LABEL[name]) || name || 'working'

export type AgentStatus = 'idle' | 'working' | 'done' | 'error'

export interface AgentView {
  role: Role
  used: boolean
  status: AgentStatus
  task?: string
  askedBy?: Role
  tool?: string
  tools: string[]
  said?: string
  findings: string[]
  recommendation?: string
  tokens?: number
}

export interface FeedItem {
  id: string
  time: string
  role?: Role | 'system'
  text: string
  tone: 'say' | 'tool' | 'error' | 'ok' | 'info'
}

export interface RunView {
  phase: 'none' | 'running' | 'finished' | 'failed'
  agents: Record<Role, AgentView>
  order: Role[]
  feed: FeedItem[]
  bossStatus?: string
  humanAction: boolean
}

const isRole = (v?: string): v is Role => !!v && (ROLES as string[]).includes(v)

function lastIndex<T>(items: T[], test: (item: T) => boolean): number {
  for (let i = items.length - 1; i >= 0; i--) if (test(items[i])) return i
  return -1
}

/** Events since the last database reset (a reset starts a fresh desk). */
export function sinceReset(events: AgentEvent[]): AgentEvent[] {
  return events.slice(lastIndex(events, (e) => e.kind === 'database_reset') + 1)
}

/** The ticket whose run happened most recently since the last reset, if any. */
export function latestRunTicket(events: AgentEvent[]): number | undefined {
  const last = [...sinceReset(events)].reverse().find((e) => e.ticket_id !== undefined && e.run_id)
  return last?.ticket_id
}

/** Every event of the newest run on this ticket. */
export function latestRunEvents(events: AgentEvent[], ticketId: number): AgentEvent[] {
  const mine = sinceReset(events).filter((e) => e.ticket_id === ticketId && e.run_id)
  if (!mine.length) return []
  const runId = mine[mine.length - 1].run_id
  return mine.filter((e) => e.run_id === runId)
}

const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })

const name = (r?: string) => (isRole(r) ? PERSONAS[r].name : (r ?? 'Someone'))

function toolDetail(e: AgentEvent): string {
  const a = e.tool_arguments ?? {}
  if (e.tool_name === 'check_inventory') return ` (${a.sku}, size ${a.size})`
  if (e.tool_name === 'update_ticket_status') return ` → ${a.status}`
  return ''
}

export function deriveRun(runEvents: AgentEvent[]): RunView {
  const blank = (role: Role): AgentView => ({ role, used: false, status: 'idle', tools: [], findings: [] })
  const agents = Object.fromEntries(ROLES.map((r) => [r, blank(r)])) as Record<Role, AgentView>
  const order: Role[] = []
  const feed: FeedItem[] = []
  let phase: RunView['phase'] = runEvents.length ? 'running' : 'none'
  let bossStatus: string | undefined
  let humanAction = false
  const pendingTask: Partial<Record<Role, { task: string; from: Role }>> = {}

  for (const e of runEvents) {
    const role = isRole(e.agent) ? e.agent : undefined
    const time = clock(e.timestamp_utc)
    switch (e.kind) {
      case 'delegation_start': {
        const to = e.agent
        if (isRole(to) && isRole(e.from_agent)) {
          pendingTask[to] = { task: e.said ?? '', from: e.from_agent }
          feed.push({
            id: e.event_id, time, role: e.from_agent, tone: 'say',
            text: `asks ${name(to)}: “${e.said ?? ''}”`,
          })
        }
        break
      }
      case 'agent_step_start':
        if (role) {
          const a = agents[role]
          a.used = true
          a.status = 'working'
          if (!order.includes(role)) order.push(role)
          const d = pendingTask[role]
          a.task = role === 'boss' ? 'Triaging the ticket' : (d?.task ?? e.said)
          a.askedBy = d?.from
          if (role === 'boss') feed.push({ id: e.event_id, time, role, tone: 'info', text: 'picked up the ticket' })
        }
        break
      case 'mcp_tool_start':
        if (role) {
          const a = agents[role]
          a.tool = toolLabel(e.tool_name)
          if (e.tool_name && !a.tools.includes(e.tool_name)) a.tools.push(e.tool_name)
          feed.push({ id: e.event_id, time, role, tone: 'tool', text: `is ${toolLabel(e.tool_name)}${toolDetail(e)}` })
        }
        break
      case 'mcp_tool_result':
        if (role) agents[role].tool = undefined
        break
      case 'mcp_tool_error':
        if (role) {
          agents[role].tool = undefined
          feed.push({ id: e.event_id, time, role, tone: 'error', text: `hit a tool error (${e.tool_name})` })
        }
        break
      case 'agent_step_finish':
        if (role) {
          const a = agents[role]
          a.status = 'done'
          a.tool = undefined
          a.said = e.said
          a.findings = e.findings ?? []
          a.recommendation = e.recommendation
          a.tokens = e.usage?.total_tokens
          if (role === 'boss') {
            bossStatus = e.recommended_status
            humanAction = !!e.human_action_required
          }
          feed.push({ id: e.event_id, time, role, tone: 'say', text: e.said ?? 'finished' })
        }
        break
      case 'agent_step_error':
        if (role) {
          agents[role].status = 'error'
          agents[role].tool = undefined
          feed.push({ id: e.event_id, time, role, tone: 'error', text: `ran into a problem (${e.error ?? 'error'})` })
        }
        break
      case 'delegation_rejected':
        feed.push({ id: e.event_id, time, role: isRole(e.from_agent) ? e.from_agent : undefined, tone: 'info', text: 'was blocked from delegating (loop limits)' })
        break
      case 'ticket_loop_finish':
        phase = 'finished'
        feed.push({ id: e.event_id, time, role: 'system', tone: 'ok', text: 'Run complete' })
        break
      case 'ticket_loop_error':
        phase = 'failed'
        feed.push({ id: e.event_id, time, role: 'system', tone: 'error', text: `Run stopped (${e.error ?? 'error'})` })
        break
    }
  }
  return { phase, agents, order, feed, bossStatus, humanAction }
}

export interface Approval {
  ticketId: number
  amount: number
  kind: string
}

/** Tickets the Boss has asked a human to approve, with the amount from its request. */
export function pendingApprovals(tickets: Ticket[], events: AgentEvent[]): Approval[] {
  const fresh = sinceReset(events)
  return tickets
    .filter((t) => t.status === 'awaiting_human_approval')
    .map((t) => {
      const req = [...fresh]
        .reverse()
        .find((e) => e.ticket_id === t.id && e.tool_name === 'request_payment_approval' && e.kind === 'mcp_tool_result' && e.tool_output?.request_recorded)
      return { ticketId: t.id, amount: Number(req?.tool_output?.amount ?? 0), kind: String(req?.tool_output?.payment_kind ?? 'payment') }
    })
}

export interface Payment {
  ticketId: number
  amount: number
  kind: string
  approvedBy: string
  time: string
}

export function paymentsMade(events: AgentEvent[]): Payment[] {
  return sinceReset(events)
    .filter((e) => e.kind === 'mcp_tool_result' && e.tool_name === 'approve_payment' && e.tool_output?.payment_made)
    .map((e) => ({
      ticketId: e.tool_output.ticket_id,
      amount: e.tool_output.amount,
      kind: e.tool_output.kind,
      approvedBy: e.tool_output.approved_by,
      time: clock(e.timestamp_utc),
    }))
}

export const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

export interface HumanAction {
  id: string
  time: string
  kind: 'payment' | 'resolution'
  text: string
}

/** What the human did on a ticket: payments approved and the written resolution. */
export function humanActions(events: AgentEvent[], ticketId: number): HumanAction[] {
  return sinceReset(events)
    .filter((e) => e.ticket_id === ticketId)
    .flatMap((e): HumanAction[] => {
      if (e.kind === 'mcp_tool_result' && e.tool_name === 'approve_payment' && e.tool_output?.payment_made) {
        const o = e.tool_output
        return [{
          id: e.event_id, time: clock(e.timestamp_utc), kind: 'payment',
          text: `${o.approved_by} approved ${money(o.amount)} (${o.kind}). Checking is now ${money(o.balance)}.`,
        }]
      }
      if (e.kind === 'human_resolution') {
        return [{ id: e.event_id, time: clock(e.timestamp_utc), kind: 'resolution', text: `${e.resolved_by} resolved it: ${e.resolution}` }]
      }
      return []
    })
}
