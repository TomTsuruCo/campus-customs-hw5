# Campus Customs MCP Server

The FastMCP server in `server.py` is the one shared shop-data interface for the Campus Customs team. It uses `../data/campus_customs_new.db`; the original `campus_customs.db` is kept as the reset source. Backend agents must use these MCP tools for every shop fact and ticket update. They must not open SQLite or create parallel shop-data tools.

## Tools

Read tools:

- `list_open_tickets()` — open rows from `tickets`.
- `check_inventory(sku, size)` — the exact matching row from `inventory`.
- `get_ticket_details(ticket_id)` — the ticket and linked `pricing`, `invoices`, `vendors`, and `leases` rows.
- `get_shop_financial_status()` — `desk`, `cash_accounts`, open `invoices`, `leases`, and `payments`.
- `list_vendors_with_shipping_status()` — `vendors` and each vendor's open `invoices`; an unpaid open invoice is flagged as a shipping block.

Ticket-writing tools:

- `append_ticket_note(ticket_id, actor, note)` appends a bounded factual work note to `tickets.notes`.
- `save_customer_draft(ticket_id, actor, draft)` stores an explicitly unsent customer-message draft in `tickets.notes`.
- `request_payment_approval(ticket_id, actor)` is Boss-only; it checks the linked database amount and available cash, records a human approval request in ticket notes, and sets the ticket to `awaiting_human_approval`. It never makes a payment.
- `update_ticket_status(ticket_id, actor, status)` allows only the Boss to change status; use `request_payment_approval` to enter the human-approval state. A ticket awaiting human payment approval cannot be moved until a human acts.

Human/dashboard tools (used only by the backend's human-click API routes; no agent role is allowed to call them):

- `list_all_tickets()` — every `tickets` row with its stored status, so the dashboard can show open vs resolved.
- `get_checking_balance()` — the `checking` row of `cash_accounts`.
- `approve_payment(ticket_id, approved_by)` — executes the payment a ticket is awaiting. It recomputes the amount from the linked invoice or lease, refuses if checking would go below zero, then lowers `cash_accounts`, inserts a `payments` row, marks the invoice paid or moves the lease `next_due` forward one month, and updates the ticket.
- `resolve_ticket(ticket_id, resolved_by, resolution)` — a human closes a ticket with a written reason; refused if the ticket is already resolved or still awaiting a payment approval.
- `reset_database()` — restores `campus_customs_new.db` from `campus_customs.db`.

All lookups use stored database values; missing values stay missing. Writes are transactional. No tool sends customer messages or contacts vendors. Agent tools never make payments: only `approve_payment`, reached through the backend's approve route after a human clicks approve, moves cash. The server runs over stdio. The backend starts it automatically; to run or register it by hand, use `python mcp_server/server.py`. `../.mcp.json` registers it for Claude Code as `campus_customs`.
