import { useEffect, useRef, useState } from 'react'
import {
  type Approval, type AgentView, type FeedItem, type HumanAction, type Payment, type RunView,
  PERSONAS, ROLES, STATUS_LABEL, money, toolLabel,
} from './derive'
import { Person } from './people'
import type { Balance, Role, Ticket } from './types'

const TYPE_ICON: Record<string, string> = { customer_order: '👕', rent_notice: '🏠', price_override: '🏷️' }
const TYPE_NAME: Record<string, string> = { customer_order: 'Customer order', rent_notice: 'Rent notice', price_override: 'Price request' }

/* ───────── Inbox: tickets as pinned paper slips ───────── */

export function TicketSlip({ ticket, selected, running, runDone, onPick }: {
  ticket: Ticket; selected: boolean; running: boolean; runDone: boolean; onPick: () => void
}) {
  const resolved = ticket.state === 'resolved'
  return (
    <button
      className={`slip status-${ticket.status} ${selected ? 'is-selected' : ''} ${resolved ? 'is-resolved' : ''}`}
      onClick={onPick}
    >
      <span className="slip-head">
        <span className="slip-icon">{TYPE_ICON[ticket.type] ?? '📄'}</span>
        <span className="slip-no">Ticket #{ticket.id}</span>
        <span className={`chip chip-${ticket.status}`}>
          {running ? <><i className="live-dot" /> Working</> : STATUS_LABEL[ticket.status]}
        </span>
      </span>
      <span className="slip-subject">{ticket.subject}</span>
      <span className="slip-meta">{TYPE_NAME[ticket.type] ?? ticket.type} · from {ticket.requester}</span>
      {ticket.sku && <span className="slip-sku">{ticket.qty ?? 1} × {ticket.sku} · size {ticket.size}</span>}
      {runDone && !resolved && !running && <span className="run-done">✓ Run complete</span>}
      {resolved && <span className="stamp">RESOLVED</span>}
    </button>
  )
}

/* ───────── The floor: one station per agent ───────── */

function Dots() {
  return <span className="dots"><i /><i /><i /></span>
}

function Station({ view, phase }: { view: AgentView; phase: RunView['phase'] }) {
  const p = PERSONAS[view.role]
  const running = phase === 'running'
  const finished = phase === 'finished' || phase === 'failed'
  const label = view.status === 'working' ? 'Working'
    : view.status === 'done' ? 'Done'
    : view.status === 'error' ? 'Stuck'
    : phase === 'none' ? 'Off shift'
    : running ? 'On standby'
    : finished ? 'Not needed' : 'Waiting'

  return (
    <article
      className={`station voice-${view.role} st-${view.status} ${view.used ? 'is-used' : phase === 'finished' || phase === 'failed' ? 'is-unused' : ''} ${running && view.status === 'working' ? 'is-live' : ''}`}
      style={{ ['--agent' as string]: p.color }}
    >
      <header>
        <span className="avatar"><Person role={view.role} label={p.name} /></span>
        <span className="who">
          <b>{p.name}</b>
          <small>{p.tag}</small>
        </span>
        <span className={`state state-${label.toLowerCase().replace(' ', '-')}`}>{label}</span>
      </header>
      <div className="bubble">
        {view.status === 'working' && (
          <>
            {view.askedBy && <p className="asked">Asked by {PERSONAS[view.askedBy].name}: “{view.task}”</p>}
            {!view.askedBy && <p className="asked">{view.task}</p>}
            <p className="doing">{view.tool ? `…${view.tool}` : '…thinking'}<Dots /></p>
          </>
        )}
        {view.status === 'done' && <p className="said">{view.said}</p>}
        {view.status === 'error' && <p className="said">Hit a snag and stopped. Check the backend log.</p>}
        {view.status === 'idle' && (
          <p className="quiet">
            {phase === 'none' ? 'Waiting for a ticket.' : finished ? 'The Boss didn’t need this desk on this ticket.' : 'Ready if the Boss calls.'}
          </p>
        )}
      </div>
      {view.tools.length > 0 && (
        <footer>
          {view.tools.map((t) => <span key={t} className="tool-chip" title={t}>{toolLabel(t)}</span>)}
        </footer>
      )}
    </article>
  )
}

export function Floor({ run }: { run: RunView }) {
  const [boss, ...rest] = ROLES
  return (
    <div className="floor">
      <Station view={run.agents[boss]} phase={run.phase} />
      <div className="spine" aria-hidden><span>delegates to</span></div>
      <div className="floor-grid">
        {rest.map((r) => <Station key={r} view={run.agents[r]} phase={run.phase} />)}
      </div>
    </div>
  )
}

/* ───────── Live feed: radio chatter ───────── */

export function Feed({ items, running }: { items: FeedItem[]; running: boolean }) {
  // Scroll only the feed itself; scrollIntoView would also scroll the whole page on every new line.
  const list = useRef<HTMLUListElement>(null)
  useEffect(() => {
    const el = list.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [items.length])
  return (
    <section className="panel feed">
      <h3>Desk chatter {running && <span className="live-pill"><i className="live-dot" /> live</span>}</h3>
      {items.length === 0 ? (
        <p className="quiet">Nothing yet. Pick a ticket and start the team.</p>
      ) : (
        <ul ref={list}>
          {items.map((it) => {
            const color = it.role && it.role !== 'system' ? PERSONAS[it.role].color : undefined
            return (
              <li key={it.id} className={`tone-${it.tone}`} style={{ ['--agent' as string]: color ?? 'var(--ink-soft)' }}>
                <time>{it.time}</time>
                <span className="who-dot" />
                <span className="line">
                  {it.role && it.role !== 'system' && <b>{PERSONAS[it.role].name} </b>}
                  {it.text}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

/* ───────── Summary: what each agent did ───────── */

export function Summary({ run, ticket, human }: { run: RunView; ticket?: Ticket; human: HumanAction[] }) {
  if (run.phase === 'none') return null
  const notCalled = ROLES.filter((r) => !run.agents[r].used)
  const bossStatus = ticket ? STATUS_LABEL[ticket.status] : ''
  return (
    <section className="panel summary">
      <h3>What each agent did</h3>
      {run.phase === 'running' && <p className="quiet">Summaries appear here as each agent signs off.</p>}
      <div className="sum-list">
        {run.order.map((r) => {
          const a = run.agents[r]
          const p = PERSONAS[r]
          if (a.status !== 'done') return null
          return (
            <article key={r} className={`sum voice-${r}`} style={{ ['--agent' as string]: p.color }}>
              <header>
                <span className="avatar sm"><Person role={r} label={p.name} /></span>
                <b>{p.name}</b>
                {a.askedBy && <small>asked by {PERSONAS[a.askedBy].name}</small>}
                {a.tokens != null && <small className="right">{a.tokens.toLocaleString()} tokens</small>}
              </header>
              <p>{a.said}</p>
              {a.findings.length > 0 && <ul>{a.findings.map((f, i) => <li key={i}>{f}</li>)}</ul>}
              {a.recommendation && <p className="rec"><b>Next:</b> {a.recommendation}</p>}
            </article>
          )
        })}
      </div>
      {human.length > 0 && (
        <div className="human-actions">
          <h4>✒︎ Human decisions</h4>
          <ul>
            {human.map((h) => (
              <li key={h.id} className={`ha-${h.kind}`}>
                <time>{h.time}</time>
                <span>{h.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {run.phase !== 'running' && (
        <p className="outcome">
          <b>Outcome:</b> {ticket?.state === 'resolved' ? 'ticket resolved ✔' : `ticket is “${bossStatus}”`}
          {run.humanAction && ' · a human decision is needed'}
        </p>
      )}
      {run.phase !== 'running' && notCalled.length > 0 && (
        <p className="not-called">
          Not called: {notCalled.map((r) => PERSONAS[r].name).join(', ')}
        </p>
      )}
    </section>
  )
}

/* ───────── Cash drawer + approval tray ───────── */

function useTween(value: number) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    const a = from.current
    const start = performance.now()
    let raf = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 1000)
      const v = a + (value - a) * (1 - Math.pow(1 - p, 3))
      from.current = v
      setShown(v)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return shown
}

export function CashDrawer({ balance, peak, payments }: { balance: Balance | null; peak: number; payments: Payment[] }) {
  const value = balance?.balance ?? 0
  const shown = useTween(value)
  const prev = useRef<number | null>(null)
  const [drop, setDrop] = useState<number | null>(null)
  useEffect(() => {
    if (balance && prev.current !== null && balance.balance < prev.current) {
      setDrop(prev.current - balance.balance)
      const t = setTimeout(() => setDrop(null), 5000)
      prev.current = balance.balance
      return () => clearTimeout(t)
    }
    if (balance) prev.current = balance.balance
  }, [balance])
  const fill = peak > 0 ? Math.max(0, Math.min(100, (value / peak) * 100)) : 0
  return (
    <section className="drawer">
      <div className="brass-plate">Checking</div>
      <div className="ledger-number">
        <span className="mono">{balance ? money(shown) : '—'}</span>
        {drop !== null && <span className="drop">−{money(drop)}</span>}
      </div>
      <div className="gauge" title="How full the cash drawer is compared to the start of the day">
        <div className="gauge-fill" style={{ width: `${fill}%` }} />
      </div>
      <p className="asof">Shop date {balance?.as_of ?? '—'} · cash only goes out in this shop</p>
      {payments.length > 0 && (
        <ul className="payments">
          {payments.map((p, i) => (
            <li key={i}>
              <span>{p.time}</span>
              <span>No. {p.ticketId} · {p.kind}</span>
              <b className="mono">−{money(p.amount)}</b>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function ApprovalTray({ approvals, tickets, approver, setApprover, busy, onApprove }: {
  approvals: Approval[]; tickets: Ticket[]; approver: string; setApprover: (v: string) => void
  busy: number | null; onApprove: (ticketId: number) => void
}) {
  return (
    <section className={`tray ${approvals.length ? 'has-items' : ''}`}>
      <h3>Signature tray</h3>
      {approvals.length === 0 ? (
        <p className="quiet">Nothing waiting. Agents can only <i>prepare</i> a payment — you’re the one who signs.</p>
      ) : (
        <>
          <label className="signer">
            Signing as
            <input value={approver} onChange={(e) => setApprover(e.target.value)} maxLength={80} />
          </label>
          {approvals.map((a) => {
            const t = tickets.find((x) => x.id === a.ticketId)
            return (
              <div className="cheque" key={a.ticketId}>
                <div className="cheque-top">
                  <span>No. {a.ticketId} · {t?.subject}</span>
                  <small>{a.kind === 'rent' ? 'Rent' : a.kind === 'invoice' ? 'Vendor invoice' : 'Payment'}</small>
                </div>
                <div className="cheque-amount mono">{money(a.amount)}</div>
                <button className="approve" disabled={busy !== null || !approver.trim()} onClick={() => onApprove(a.ticketId)}>
                  {busy === a.ticketId ? 'Signing…' : '✒︎ Approve & pay'}
                </button>
              </div>
            )
          })}
        </>
      )}
    </section>
  )
}

export type { Role }
