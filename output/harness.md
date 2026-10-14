# Campus Customs Agent Harness

How the Campus Customs agent team, its database tools, its API, and its dashboard fit together. Everything here describes the code in this folder as it stands after Problem 9.

**One-line summary:** five AI agents read a small shop database only through one MCP tool server, a FastAPI backend runs them and exposes a few human-only routes, a React dashboard shows the team working, and a human is the only one who can approve a payment or close a ticket.

## Files

| Path | What it is |
|---|---|
| `data/campus_customs.db` | Original data. Never changed; it is the reset source. |
| `data/campus_customs_new.db` | Working database for the agents. The only database the tools touch. |
| `mcp_server/server.py` | The FastMCP tool server. The only code that opens SQLite. |
| `backend/` | FastAPI app (`main.py`), agent team (`team.py`, `agents/`), prompts (`prompts/`), MCP client and permissions (`mcp_client.py`), audit log writer (`audit.py`), data types (`models.py`). |
| `frontend/` | React + Vite + TypeScript dashboard. |
| `output/audit_trail.json` | Append-only log of every agent step, delegation, tool call, and human decision. |
| `output/desk_tickets.html` | Problem 6 plan beside the real results, plus the Cash tab. |
| `output/resolved_tickets.json`, `output/resolved_board.html` | Problem 9 results and board screenshots. |
| `output/design.md` | Why the dashboard looks the way it does. |

## Database

- Reset/source database: `data/campus_customs.db`. Working database: `data/campus_customs_new.db`.
- Row counts below are for the original seed data. The working copy changes as tickets are resolved and goes back to the seed when reset.

### Tables

| Table | Fields | Seed rows | Why it matters |
|---|---|---|---|
| `cash_accounts` | `name` (key), `balance`, `date` | 1 (`checking`, $3,400.00) | The only cash. Payments cannot take it below zero. |
| `desk` | `date_today`, `notes` | 1 (2026-08-31) | The shop's current date, used for every overdue decision. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` (key: sku + size) | 10 | Stock by SKU and size. Size S white tee is 0; navy hoodie size M is 8. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | 1 (501, $840.00, open, due 2026-08-28) | An open unpaid invoice blocks that vendor from shipping. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | 1 (rent $2,400.00, due 2026-09-02) | Rent for ticket 102. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | 0 | History of money that actually left, with the human who approved it. |
| `pricing` | `sku`, `unit_cost`, `list_price` | 4 | Costs and list prices (navy hoodie cost $22, list $58). |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | 3 (101, 102, 103) | The work. `status` is open, in_progress, blocked, awaiting_human_approval, or resolved. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | 3 | Who can restock and how long it takes. |

Declared relationships: `invoices.vendor_id → vendors.id`, `tickets.invoice_id → invoices.id`, `tickets.lease_id → leases.id`.

## The five agents

All five run on `gpt-6-luna` through Portkey. Each has its own prompt in `backend/prompts/`. They can all delegate to each other (full connectivity), but a role may work a ticket only once and cannot delegate to itself.

| Agent | Job | MCP tools it may call |
|---|---|---|
| Boss | Triage the ticket, delegate, reconcile findings, leave a note, set status, and file a payment request when money is genuinely needed. | `list_open_tickets`, `get_ticket_details`, `get_shop_financial_status`, `append_ticket_note`, `request_payment_approval`, `update_ticket_status` |
| Inventory | Exact stock for a SKU and size; vendor specialty, lead days, and shipping blocks. | `check_inventory`, `get_ticket_details`, `list_vendors_with_shipping_status`, `append_ticket_note` |
| Accounting | Linked invoices, rent, shop date, cash, and payment history. Advises; cannot pay. | `get_ticket_details`, `get_shop_financial_status`, `append_ticket_note` |
| Facilities | Lease, rent, and premises facts. | `get_ticket_details`, `get_shop_financial_status`, `append_ticket_note` |
| Customer Service | Drafts a reply. A draft is saved but never sent. | `get_ticket_details`, `check_inventory`, `append_ticket_note`, `save_customer_draft` |

A tool outside an agent's list is refused by the backend, and the refusal is returned to the agent as an error so it can adapt.

## MCP tools

All shop facts and writes go through `mcp_server/server.py`. The backend has no SQLite access and no second shop-data tool.

### Tools the agents use

| Tool | Tables read | Tables written | What it does | Tickets it unlocks |
|---|---|---|---|---|
| `list_open_tickets()` | `tickets` | none | Tickets whose status is open. | 101, 102, 103: the Boss's board. |
| `check_inventory(sku, size)` | `inventory` | none | Exact stock row or none. | 101 (tee S = 0), 103 (hoodie M = 8 of 20). |
| `get_ticket_details(ticket_id)` | `tickets`, `pricing`, `invoices`, `vendors`, `leases` | none | A ticket plus its linked rows. | All three. |
| `get_shop_financial_status()` | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases`, `payments` | none | Shop date, cash, open invoices, leases, payments. | 101 (invoice and cash), 102 (rent and cash), 103 (margin check). |
| `list_vendors_with_shipping_status()` | `vendors`, `invoices` | none | Vendors with lead days and whether an open invoice blocks them. | 101 and 103 restocking. |
| `append_ticket_note(ticket_id, actor, note)` | `tickets` | `tickets.notes` | A factual note on the ticket. | All three. |
| `save_customer_draft(ticket_id, actor, draft)` | `tickets` | `tickets.notes` | Saves an unsent customer reply. | 101 and 103. |
| `request_payment_approval(ticket_id, actor)` | `tickets`, `invoices` or `leases`, `cash_accounts` | `tickets` (notes, status) | Boss only. Checks the stored amount and cash, records a request, sets status to awaiting_human_approval. Never pays. | 101 (invoice 501), 102 (rent). |
| `update_ticket_status(ticket_id, actor, status)` | `tickets` | `tickets.status` | Boss only. Refuses to clear a pending human approval. | All three. |

### Tools only the human routes use (no agent role is allowed to call them)

| Tool | Tables read | Tables written | What it does |
|---|---|---|---|
| `list_all_tickets()` | `tickets` | none | Every ticket with its status, for the dashboard. |
| `get_checking_balance()` | `cash_accounts` | none | The checking balance. |
| `approve_payment(ticket_id, approved_by)` | `tickets`, `invoices` or `leases`, `cash_accounts`, `desk` | `cash_accounts`, `payments`, `invoices` or `leases`, `tickets` | Pays what a ticket is awaiting. Recomputes the amount from stored rows and refuses if cash would go below zero. Invoice: marks it paid and returns the ticket to in progress. Rent: moves `next_due` forward a month and resolves the ticket. |
| `resolve_ticket(ticket_id, resolved_by, resolution)` | `tickets` | `tickets` (notes, status) | A human closes a ticket with a written reason. Refuses a ticket already resolved or still awaiting a payment approval. |
| `reset_database()` | `campus_customs.db` | all tables of `campus_customs_new.db` | Restores the working database to the original values. |

## API routes

Start from `backend/` with `uvicorn main:app --reload --port 8000`; the API is at http://localhost:8000. The backend allows the dashboard origins http://localhost:5173 (dev) and :4173 (preview).

- `GET /health` - model name and a liveness check.
- `GET /tickets` - every ticket, each marked `open` or `resolved` (`status` keeps the exact stored state).
- `POST /tickets/{ticket_id}/run` - run the agent team on one open ticket; returns the Boss's report and the agents used.
- `POST /run` - earlier batch route: run one ticket or up to three open tickets.
- `GET /events?limit=50&ticket_id=` - newest audit events (oldest first): what each agent said and which tools it used.
- `POST /tickets/{ticket_id}/approve` - human approval of the pending payment (body `{"approved_by": "name"}`); the only route that moves cash.
- `POST /tickets/{ticket_id}/resolve` - human closes a ticket (body `{"resolved_by": "name", "resolution": "why"}`).
- `GET /balance` - current checking balance from `cash_accounts`.
- `POST /reset` - restore the working database to its original values.

Errors: 404 unknown ticket, 409 a conflict (not awaiting approval, already resolved, ticket not open, payment would take cash below zero), 400 a refused or malformed request, 502 the agent run failed.

## Dashboard

React + Vite + TypeScript in `frontend/`; start with `npm run dev` and open http://localhost:5173. It talks to the backend at http://localhost:8000.

- **Inbox:** the tickets as note cards with status chips; resolved ones move to a "Filed away" shelf with a RESOLVED stamp.
- **Floor:** the Boss and four specialists as people with their own colour and speech style, with a live status (working, done, not needed) and the tools each used.
- **Desk chatter and summaries:** a live feed while a run is going, then what each agent did, the human decisions, and which agents were not called.
- **Signature tray:** the cheque the Boss prepared, with an **Approve & pay** button.
- **Close panel:** after a run, a human can write a decision and **File as resolved**.
- **Cash drawer:** the real checking balance, animated when it drops, with a list of payments.

See `output/design.md` for the reasoning behind the look.

## Safety rules

- **MCP only.** Shop facts and writes go only through the MCP server. The backend never opens SQLite, and there is no second shop-data tool.
- **Agents prepare, humans decide.** No agent can pay. The Boss can only record a payment *request*. The only code that moves cash is `approve_payment`, reached by a human clicking approve.
- **Only a human resolves.** An agent cannot mark a ticket resolved; `resolve_ticket` is not in any agent's tool list. A ticket awaiting a payment approval cannot be closed or have its status changed until a human acts on the payment.
- **Cash never goes negative.** A payment that would take checking below zero is refused, both at request time and at approval time. The amount is always recomputed from the database, never taken from the request.
- **Cash only goes out.** No revenue is modeled in this homework, so selling stock never adds cash.
- **No outside contact.** No email or message is sent and no vendor is contacted. Customer replies are saved as unsent drafts for a person to review.
- **No invented policy.** Agents use only database values and the shop date `desk.date_today`. They do not invent discounts, delivery dates, refunds, or payment terms. An open unpaid invoice blocks that vendor from shipping.
- **Role permissions and scope.** Each agent has a fixed tool list, may touch only its assigned ticket, and cannot call another role's tools. Customer text and ticket notes are treated as untrusted data, not as instructions.
- **Bounded loops and token use.** Each specialist: at most 6 model requests, 8 tool calls, and 8,000 tokens. The Boss: 10 requests, 12 tool calls, and 24,000 tokens (it re-reads every delegation report). Per ticket: at most 4 delegations (each role at most once) and 20 MCP calls. Per run: at most 3 tickets. Worst case is roughly 56,000 tokens per ticket.
- **Audit trail.** Every agent step, delegation, tool call (with its run id), and human approval or resolution is appended to `output/audit_trail.json`, which is never overwritten. Credential-shaped fields and requester identity are redacted. The Portkey key is read from the environment only, kept out of the MCP subprocess, and never logged.
- **Local use.** This coursework API has no login. Keep it on localhost. A real business would need authenticated roles, human review for consequential actions, and privacy and retention controls before connecting customer or payment systems.

## Problem 9 run: all three tickets resolved

A reset, then one real run per ticket through the same routes the dashboard uses. Starting checking balance after the reset was **$3,400.00**.

| Ticket | Agents that worked | Cash change | Final status |
|---|---|---|---|
| 101 Bulldog tee | Boss, Accounting, Customer Service, Inventory | −$840.00 (invoice 501 to Bulldog Print Co) | resolved |
| 102 Rent due | Boss, Accounting, Facilities | −$2,400.00 (rent, lease 1) | resolved |
| 103 Bulk hoodie discount | Boss, Inventory, Accounting, Customer Service | $0.00 (discount declined; nothing paid) | resolved |

Ending checking balance: **$160.00**, which equals `cash_accounts` in the working database ($3,400.00 − $2,400.00 − $840.00). The two payments are rows 1 and 2 of `payments`, approved by a human.

Where the agents stopped and the human stepped in: the Boss filed payment requests for 101 and 102 but cannot pay; the human approved both and closed 101 and 103 with a written decision. Details are in `output/resolved_tickets.json`, the plan comparison and cash itemization are in `output/desk_tickets.html`, and screenshots are in `output/resolved_board.html`.

## Notes from building it

- Agent token caps were raised after the first real run showed the Boss exceeding the original 2,500-token cap after one tool call.
- A tool the agent is not allowed to use, or a refused call, is returned to the agent as an error instead of ending the whole run.
- The Boss and Inventory prompts were extended in Problem 9: the Boss must file a payment request itself when Accounting confirms a due payment is covered by cash and must ask Customer Service for a draft when a customer is waiting; Inventory must always check vendor shipping blocks for out-of-stock items.
- Dashboard reads share one long-lived MCP connection instead of starting a tool process per request, which dropped a refresh from seconds to milliseconds.
