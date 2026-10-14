import type { AgentEvent, ApprovalResult, Balance, RunResult, Ticket } from './types'

/** The dashboard talks to the Campus Customs backend here. */
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_URL + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(`Can't reach the backend at ${API_URL}. Is uvicorn running?`, 0)
  }
  const text = await res.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const body = data as { detail?: unknown; reason?: string } | null
    const detail =
      typeof body?.detail === 'string'
        ? body.detail
        : body?.reason === 'insufficient_cash'
          ? 'Not enough cash in checking to make that payment.'
          : res.statusText || `HTTP ${res.status}`
    throw new ApiError(detail, res.status)
  }
  return data as T
}

export const api = {
  tickets: () => request<Ticket[]>('/tickets'),
  balance: () => request<Balance>('/balance'),
  events: (limit = 200) => request<{ events: AgentEvent[] }>(`/events?limit=${limit}`),
  run: (ticketId: number) => request<RunResult>(`/tickets/${ticketId}/run`, { method: 'POST' }),
  approve: (ticketId: number, approvedBy: string) =>
    request<ApprovalResult>(`/tickets/${ticketId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  resolve: (ticketId: number, resolvedBy: string, resolution: string) =>
    request<{ status: string }>(`/tickets/${ticketId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolved_by: resolvedBy, resolution }),
    }),
  reset: () => request<{ reset: boolean }>('/reset', { method: 'POST' }),
}
