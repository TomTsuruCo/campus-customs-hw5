import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, API_URL } from './api'
import { ApprovalTray, CashDrawer, Feed, Floor, Summary, TicketSlip } from './components'
import { YaleBadge } from './people'
import { ROLES, deriveRun, humanActions, latestRunEvents, latestRunTicket, paymentsMade, pendingApprovals, sinceReset, money } from './derive'
import type { AgentEvent, Balance, Ticket } from './types'

type Toast = { kind: 'ok' | 'error'; text: string }

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [balance, setBalance] = useState<Balance | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [running, setRunning] = useState<number | null>(null)
  const [approving, setApproving] = useState<number | null>(null)
  const [closing, setClosing] = useState<number | null>(null)
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [offline, setOffline] = useState(false)
  const [toast, setToast] = useState<Toast | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('approver') ?? 'Tom')
  const peak = useRef(0)

  // Responses can arrive out of order (a slow full refresh may finish after a newer events poll), so
  // every request is numbered and an older response never overwrites newer state.
  const seq = useRef(0)
  const appliedFull = useRef(0)
  const appliedEvents = useRef(0)

  const refresh = useCallback(async () => {
    const mine = ++seq.current
    try {
      const [t, b, e] = await Promise.all([api.tickets(), api.balance(), api.events(200)])
      if (mine > appliedEvents.current) {
        appliedEvents.current = mine
        setEvents(e.events)
      }
      if (mine > appliedFull.current) {
        appliedFull.current = mine
        setTickets(t)
        setBalance(b)
        setOffline(false)
        peak.current = Math.max(peak.current, b.balance)
        const linked = Number(new URLSearchParams(window.location.search).get('ticket'))
        setSelected((s) => s ?? (t.some((x) => x.id === linked) ? linked : undefined) ?? latestRunTicket(e.events) ?? t[0]?.id ?? null)
      }
    } catch {
      setOffline(true)
    }
  }, [])

  // Only the event feed is cheap to read, so while the team runs it is polled fast (that is what makes
  // the floor feel live) and tickets/balance are refreshed at a slower pace.
  const refreshEvents = useCallback(async () => {
    try {
      const mine = ++seq.current
      const e = await api.events(200)
      if (mine > appliedEvents.current) {
        appliedEvents.current = mine
        setEvents(e.events)
      }
    } catch {
      /* the slower full refresh reports being offline */
    }
  }, [])

  useEffect(() => {
    refresh()
    const full = setInterval(refresh, running !== null ? 5000 : 4000)
    const live = running !== null ? setInterval(refreshEvents, 800) : undefined
    return () => {
      clearInterval(full)
      if (live) clearInterval(live)
    }
  }, [refresh, refreshEvents, running])

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 6000)
    return () => clearTimeout(id)
  }, [toast])

  useEffect(() => localStorage.setItem('approver', approver), [approver])

  const ticket = tickets.find((t) => t.id === selected)
  const run = useMemo(
    () => deriveRun(selected === null ? [] : latestRunEvents(events, selected)),
    [events, selected],
  )
  const human = useMemo(() => (selected === null ? [] : humanActions(events, selected)), [events, selected])
  const approvals = useMemo(() => pendingApprovals(tickets, events), [tickets, events])
  const payments = useMemo(() => paymentsMade(events), [events])
  const finishedRuns = useMemo(
    () => new Set(sinceReset(events).filter((e) => e.kind === 'ticket_loop_finish').map((e) => e.ticket_id)),
    [events],
  )
  const open = tickets.filter((t) => t.state === 'open')
  const filed = tickets.filter((t) => t.state === 'resolved')
  const canStart = ticket?.status === 'open' && running === null && !offline

  async function startTeam() {
    if (!ticket) return
    const id = ticket.id
    setRunning(id)
    try {
      await api.run(id)
      await refreshEvents() // pull the final events first so the floor is up to date when the toast shows
      setToast({ kind: 'ok', text: `Team finished ticket No. ${id}.` })
    } catch (e) {
      setToast({ kind: 'error', text: e instanceof ApiError ? e.message : 'The run failed.' })
    } finally {
      setRunning(null)
      refresh()
    }
  }

  async function approve(id: number) {
    setApproving(id)
    try {
      const r = await api.approve(id, approver.trim())
      // Show the result right away instead of waiting for the next refresh.
      setBalance((b) => (b ? { ...b, balance: r.balance } : b))
      setTickets((ts) => ts.map((t) => (t.id === id && r.ticket_status
        ? { ...t, status: r.ticket_status as Ticket['status'], state: r.ticket_status === 'resolved' ? 'resolved' : 'open' }
        : t)))
      setToast({ kind: 'ok', text: `Paid ${money(r.amount)}. Checking is now ${money(r.balance)}.` })
    } catch (e) {
      setToast({ kind: 'error', text: e instanceof ApiError ? e.message : 'Approval failed.' })
    } finally {
      setApproving(null)
      refresh()
    }
  }

  async function closeTicket(id: number) {
    const resolution = (notes[id] ?? '').trim()
    if (!resolution) return
    setClosing(id)
    try {
      await api.resolve(id, approver.trim(), resolution)
      setTickets((ts) => ts.map((t) => (t.id === id ? { ...t, status: 'resolved', state: 'resolved' } : t)))
      setNotes((n) => ({ ...n, [id]: '' }))
      setToast({ kind: 'ok', text: `Ticket No. ${id} filed as resolved.` })
    } catch (e) {
      setToast({ kind: 'error', text: e instanceof ApiError ? e.message : 'Could not close the ticket.' })
    } finally {
      setClosing(null)
      refresh()
    }
  }

  async function reset() {
    if (!window.confirm('Reset the desk to its original state? Tickets reopen and the cash drawer refills.')) return
    try {
      await api.reset()
      peak.current = 0
      setToast({ kind: 'ok', text: 'Fresh desk. Everything is back to the start of the day.' })
    } catch (e) {
      setToast({ kind: 'error', text: e instanceof ApiError ? e.message : 'Reset failed.' })
    }
    refresh()
  }

  // Built from the real data, so it follows however many tickets the backend returns.
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
  const tagline = tickets.length === 0
    ? 'Opening the desk…'
    : `${plural(ROLES.length, 'agent')}, ${plural(tickets.length, 'ticket')} (${open.length} open), one human who signs the checks.`

  const startLabel = running === selected && running !== null ? 'Team is working…'
    : !ticket || ticket.status === 'open' ? 'Start the team'
    : ticket?.state === 'resolved' ? 'Filed away'
    : ticket?.status === 'awaiting_human_approval' ? 'Waiting for your OK'
    : 'Run finished'

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">🗂️</span>
          <div>
            <h1>Campus Customs <em>· The Desk</em></h1>
            <p>{tagline}</p>
          </div>
        </div>
        <div className="top-actions">
          <span className={`conn ${offline ? 'is-off' : 'is-on'}`} title={API_URL}>
            <i className="live-dot" /> {offline ? 'Backend offline' : 'Backend connected'}
          </span>
          <button className="ghost" onClick={reset} disabled={running !== null || offline}>↺ Fresh desk</button>
          <YaleBadge />
        </div>
      </header>

      {offline && (
        <div className="banner">
          Can’t reach the backend at <code>{API_URL}</code>. In the <code>backend</code> folder run{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="desk">
        <aside className="inbox">
          <h2>Inbox</h2>
          {open.map((t) => (
            <TicketSlip key={t.id} ticket={t} selected={t.id === selected} running={running === t.id} runDone={finishedRuns.has(t.id)} onPick={() => setSelected(t.id)} />
          ))}
          {filed.length > 0 && (
            <>
              <h2 className="filed-h">Filed away</h2>
              {filed.map((t) => (
                <TicketSlip key={t.id} ticket={t} selected={t.id === selected} running={false} runDone={finishedRuns.has(t.id)} onPick={() => setSelected(t.id)} />
              ))}
            </>
          )}
          {tickets.length === 0 && !offline && <p className="quiet">Loading the inbox…</p>}
        </aside>

        <section className="center">
          <div className="case">
            <div className="case-head">
              <div>
                <small>{ticket ? `Ticket No. ${ticket.id}` : 'No ticket picked'}</small>
                <h2>{ticket?.subject ?? 'Pick a ticket from the inbox'}</h2>
              </div>
              {ticket?.state !== 'resolved' && (
                <button className="go" disabled={!canStart} onClick={startTeam}>
                  {running !== null && running === selected && <i className="spinner" />}
                  {startLabel}
                </button>
              )}
            </div>
            {ticket && ticket.status !== 'open' && ticket.state !== 'resolved' && running === null && (
              <p className="hint">
                {ticket.status === 'awaiting_human_approval'
                  ? <>The Boss has prepared a payment. Approve it in the <b>signature tray</b> on the right.</>
                  : <>The team has finished its run. If a human decision settles this ticket, write it below and file it as resolved (or use <b>Fresh desk</b> to start over).</>}
              </p>
            )}
            {ticket && (ticket.status === 'blocked' || ticket.status === 'in_progress' || (ticket.status === 'open' && finishedRuns.has(ticket.id))) && running === null && (
              <div className="closer">
                <label htmlFor="close-note">Your decision, recorded on the ticket under “{approver.trim() || 'your name'}”</label>
                <textarea
                  id="close-note" rows={3} maxLength={900}
                  placeholder="What was decided and why, for example what the customer is told…"
                  value={notes[ticket.id] ?? ''}
                  onChange={(e) => setNotes((n) => ({ ...n, [ticket.id]: e.target.value }))}
                />
                <button
                  className="file"
                  disabled={closing !== null || !(notes[ticket.id] ?? '').trim() || !approver.trim()}
                  onClick={() => closeTicket(ticket.id)}
                >
                  {closing === ticket.id ? 'Filing…' : '✓ File as resolved'}
                </button>
              </div>
            )}
            {ticket?.state === 'resolved' && <div className="big-stamp">RESOLVED</div>}
          </div>
          <Floor run={run} />
          <div className={`lower ${run.phase === 'none' ? 'solo' : ''}`}>
            <Feed items={run.feed} running={run.phase === 'running'} />
            <Summary run={run} ticket={ticket} human={human} />
          </div>
        </section>

        <aside className="money">
          <CashDrawer balance={balance} peak={peak.current} payments={payments} />
          <ApprovalTray
            approvals={approvals} tickets={tickets} approver={approver} setApprover={setApprover}
            busy={approving} onApprove={approve}
          />
        </aside>
      </main>

      {toast && <div className={`toast toast-${toast.kind}`} onClick={() => setToast(null)}>{toast.text}</div>}
    </div>
  )
}
