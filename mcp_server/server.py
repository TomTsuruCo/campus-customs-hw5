"""Shared MCP tools for reading and carefully updating Campus Customs tickets."""

import calendar
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Literal

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "campus_customs_new.db"
SOURCE_DATABASE_PATH = PROJECT_ROOT / "data" / "campus_customs.db"
AgentRole = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["in_progress", "blocked", "awaiting_human_approval", "resolved"]

mcp = FastMCP("Campus Customs Operations")


@contextmanager
def _database(*, read_only: bool = True) -> Iterator[sqlite3.Connection]:
    """Open the configured working database, read-only unless a tool must write."""
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Campus Customs database not found: {DATABASE_PATH}")

    connection = sqlite3.connect(
        f"{DATABASE_PATH.as_uri()}?mode={'ro' if read_only else 'rw'}",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        if not read_only:
            connection.commit()
    except Exception:
        if not read_only:
            connection.rollback()
        raise
    finally:
        connection.close()


def _cash_balance(connection: sqlite3.Connection) -> float:
    row = connection.execute("SELECT COALESCE(SUM(balance), 0) FROM cash_accounts").fetchone()
    return float(row[0])


def _ticket(connection: sqlite3.Connection, ticket_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise ValueError(f"Ticket {ticket_id} was not found in the working database.")
    return row


def _append_note(connection: sqlite3.Connection, ticket_id: int, actor: str, note: str) -> str:
    if not note.strip() or len(note) > 1200:
        raise ValueError("A ticket note must contain 1 to 1200 characters.")
    row = _ticket(connection, ticket_id)
    if row["status"] == "resolved":
        raise ValueError(f"Ticket {ticket_id} is resolved and cannot receive new notes.")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    entry = f"[{timestamp}] [{actor}] {note.strip()}"
    previous = row["notes"] or ""
    combined = f"{previous.rstrip()}\n{entry}".strip()
    connection.execute("UPDATE tickets SET notes = ? WHERE id = ?", (combined, ticket_id))
    return entry


def _payment_target(connection: sqlite3.Connection, ticket: sqlite3.Row) -> tuple[str, int, float]:
    """Return (kind, reference id, amount) of what a ticket would pay, from stored rows only."""
    if ticket["invoice_id"] is not None:
        reference_id = int(ticket["invoice_id"])
        reference = connection.execute(
            "SELECT id, vendor_id, amount, status FROM invoices WHERE id = ?",
            (reference_id,),
        ).fetchone()
        if reference is None or reference["status"] != "open":
            raise ValueError("The ticket's linked invoice is not open in the working database.")
        return "invoice", reference_id, float(reference["amount"])
    if ticket["lease_id"] is not None:
        reference_id = int(ticket["lease_id"])
        reference = connection.execute(
            "SELECT id, monthly_rent AS amount FROM leases WHERE id = ?",
            (reference_id,),
        ).fetchone()
        if reference is None:
            raise ValueError("The ticket's linked lease was not found in the working database.")
        return "rent", reference_id, float(reference["amount"])
    raise ValueError("The ticket has no linked open invoice or lease to request payment for.")


def _next_month(iso_date: str) -> str:
    """Advance a YYYY-MM-DD date by one calendar month, clamping the day."""
    year, month, day = (int(part) for part in iso_date.split("-"))
    year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{year:04d}-{month:02d}-{min(day, calendar.monthrange(year, month)[1]):02d}"


@mcp.tool()
def list_open_tickets() -> list[dict[str, Any]]:
    """Return every ticket whose stored status is open, ordered by ticket ID."""
    with _database() as connection:
        rows = connection.execute(
            "SELECT * FROM tickets WHERE status = ? ORDER BY id",
            ("open",),
        ).fetchall()
    return [dict(row) for row in rows]


@mcp.tool()
def check_inventory(sku: str, size: str) -> dict[str, Any] | None:
    """Look up the exact SKU and size; return its stored inventory row or None."""
    with _database() as connection:
        row = connection.execute(
            """
            SELECT sku, name, size, qty, location
            FROM inventory
            WHERE sku = ? AND size = ?
            """,
            (sku, size),
        ).fetchone()
    return dict(row) if row is not None else None


@mcp.tool()
def get_ticket_details(ticket_id: int) -> dict[str, Any] | None:
    """Return a ticket and its stored pricing, invoice/vendor, and lease context."""
    with _database() as connection:
        ticket = connection.execute(
            "SELECT * FROM tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        if ticket is None:
            return None

        ticket_data = dict(ticket)
        sku = ticket_data["sku"]
        invoice_id = ticket_data["invoice_id"]
        lease_id = ticket_data["lease_id"]

        pricing = None
        if sku is not None:
            row = connection.execute(
                "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
                (sku,),
            ).fetchone()
            pricing = dict(row) if row is not None else None

        invoice = None
        vendor = None
        if invoice_id is not None:
            row = connection.execute(
                "SELECT * FROM invoices WHERE id = ?",
                (invoice_id,),
            ).fetchone()
            if row is not None:
                invoice = dict(row)
                vendor_row = connection.execute(
                    "SELECT * FROM vendors WHERE id = ?",
                    (invoice["vendor_id"],),
                ).fetchone()
                vendor = dict(vendor_row) if vendor_row is not None else None

        lease = None
        if lease_id is not None:
            row = connection.execute(
                "SELECT * FROM leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
            lease = dict(row) if row is not None else None

    return {
        "ticket": ticket_data,
        "pricing": pricing,
        "invoice": invoice,
        "vendor": vendor,
        "lease": lease,
    }


@mcp.tool()
def get_shop_financial_status() -> dict[str, Any]:
    """Read the shop date, cash accounts, open invoices, leases, and payment history."""
    with _database() as connection:
        desk = connection.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
        cash = connection.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name").fetchall()
        invoices = connection.execute(
            """
            SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date,
                   i.status, i.description
            FROM invoices AS i
            JOIN vendors AS v ON v.id = i.vendor_id
            WHERE i.status = 'open'
            ORDER BY i.id
            """
        ).fetchall()
        leases = connection.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases ORDER BY id"
        ).fetchall()
        payments = connection.execute(
            "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments ORDER BY id"
        ).fetchall()
    return {
        "desk": dict(desk) if desk is not None else None,
        "cash_accounts": [dict(row) for row in cash],
        "available_cash": sum(float(row["balance"]) for row in cash),
        "open_invoices": [dict(row) for row in invoices],
        "leases": [dict(row) for row in leases],
        "payments": [dict(row) for row in payments],
    }


@mcp.tool()
def list_vendors_with_shipping_status() -> list[dict[str, Any]]:
    """List stored vendor specialties and lead times plus open-invoice shipping blocks."""
    with _database() as connection:
        vendors = connection.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
        result = []
        for vendor in vendors:
            open_invoices = connection.execute(
                "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY id",
                (vendor["id"],),
            ).fetchall()
            result.append(
                {
                    **dict(vendor),
                    "open_unpaid_invoices": [dict(row) for row in open_invoices],
                    "can_ship_new_products": len(open_invoices) == 0,
                }
            )
    return result


@mcp.tool()
def append_ticket_note(ticket_id: int, actor: AgentRole, note: str) -> dict[str, Any]:
    """Append an agent's factual finding or work note to the ticket board."""
    with _database(read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        entry = _append_note(connection, ticket_id, actor, note)
    return {"ticket_id": ticket_id, "actor": actor, "note_added": True, "entry": entry}


@mcp.tool()
def save_customer_draft(ticket_id: int, actor: Literal["customer_service"], draft: str) -> dict[str, Any]:
    """Save a customer message draft on its ticket; this tool never sends messages."""
    if not draft.strip() or len(draft) > 1000:
        raise ValueError("A customer draft must contain 1 to 1000 characters.")
    note = f"Customer message draft (not sent): {draft.strip()}"
    with _database(read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        entry = _append_note(connection, ticket_id, actor, note)
    return {"ticket_id": ticket_id, "draft_saved": True, "sent": False, "entry": entry}


@mcp.tool()
def request_payment_approval(
    ticket_id: int,
    actor: Literal["boss"],
) -> dict[str, Any]:
    """Let only the Boss record a human approval request; this tool never pays."""
    with _database(read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket = _ticket(connection, ticket_id)
        if ticket["status"] in ("resolved", "awaiting_human_approval"):
            raise ValueError(f"Ticket {ticket_id} is not eligible for a new payment approval request.")

        payment_kind, reference_id, amount = _payment_target(connection, ticket)

        available_cash = _cash_balance(connection)
        if amount <= 0:
            raise ValueError("The database amount must be positive before requesting payment approval.")
        if amount > available_cash:
            return {
                "request_recorded": False,
                "payment_made": False,
                "refused": True,
                "reason": "insufficient_cash",
                "ticket_id": ticket_id,
                "payment_kind": payment_kind,
                "reference_id": reference_id,
                "amount": amount,
                "available_cash": available_cash,
            }

        note = (
            f"Human payment approval requested by {actor}; {payment_kind} reference {reference_id}; "
            f"database amount {amount}; available cash {available_cash}. No payment has been made."
        )
        entry = _append_note(connection, ticket_id, actor, note)
        connection.execute(
            "UPDATE tickets SET status = 'awaiting_human_approval' WHERE id = ?",
            (ticket_id,),
        )
    return {
        "request_recorded": True,
        "payment_made": False,
        "ticket_id": ticket_id,
        "payment_kind": payment_kind,
        "reference_id": reference_id,
        "amount": amount,
        "available_cash": available_cash,
        "status": "awaiting_human_approval",
        "entry": entry,
    }


@mcp.tool()
def update_ticket_status(ticket_id: int, actor: Literal["boss"], status: TicketStatus) -> dict[str, Any]:
    """Let the Boss record a final ticket state; never resolves a pending payment request."""
    with _database(read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket = _ticket(connection, ticket_id)
        if ticket["status"] == "resolved" and status != "resolved":
            raise ValueError(f"Ticket {ticket_id} is already resolved and cannot be reopened by this tool.")
        if status == "awaiting_human_approval" and ticket["status"] != "awaiting_human_approval":
            raise ValueError("Use request_payment_approval to record a human approval request and set this status.")
        if ticket["status"] == "awaiting_human_approval" and status != "awaiting_human_approval":
            raise ValueError("A ticket awaiting human payment approval cannot change status until a human acts.")
        connection.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
    return {"ticket_id": ticket_id, "actor": actor, "status": status}


# --- Dashboard/API tools -------------------------------------------------------------------
# These serve the human-facing backend routes (Problem 7). They are NOT in any agent's tool
# list in backend/mcp_client.py, so agents can never approve a payment or reset the database.


@mcp.tool()
def list_all_tickets() -> list[dict[str, Any]]:
    """Return every ticket with its stored status so a dashboard can show open vs resolved."""
    with _database() as connection:
        rows = connection.execute(
            "SELECT id, type, requester, subject, sku, size, qty, status, created_at FROM tickets ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


@mcp.tool()
def get_checking_balance() -> dict[str, Any]:
    """Return the stored checking-account balance and its as-of date."""
    with _database() as connection:
        row = connection.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
    if row is None:
        raise ValueError("No checking account exists in cash_accounts.")
    return {"account": row["name"], "balance": float(row["balance"]), "as_of": row["date"]}


@mcp.tool()
def approve_payment(ticket_id: int, approved_by: str) -> dict[str, Any]:
    """Execute the payment a ticket is awaiting after a human approves it.

    Only for the human-click API route. Recomputes the amount from stored rows, refuses if it
    would take checking below zero, then updates cash, payments, and the paid invoice or lease.
    """
    approver = approved_by.strip()
    if not approver or len(approver) > 80:
        raise ValueError("approved_by must be 1 to 80 characters naming the human approver.")
    with _database(read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket = _ticket(connection, ticket_id)
        if ticket["status"] != "awaiting_human_approval":
            raise ValueError(f"Ticket {ticket_id} is not awaiting human payment approval.")
        kind, reference_id, amount = _payment_target(connection, ticket)
        checking = connection.execute(
            "SELECT balance FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()
        if checking is None:
            raise ValueError("No checking account exists in cash_accounts.")
        balance = float(checking["balance"])
        if amount <= 0:
            raise ValueError("The database amount must be positive before a payment can be made.")
        if amount > balance:
            return {
                "payment_made": False,
                "refused": True,
                "reason": "insufficient_cash",
                "ticket_id": ticket_id,
                "amount": amount,
                "balance": balance,
            }
        today = connection.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]
        new_balance = balance - amount
        connection.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = 'checking'",
            (new_balance, today),
        )
        cursor = connection.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, 'checking', ?, ?)",
            (kind, reference_id, amount, today, approver),
        )
        if kind == "invoice":
            connection.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (reference_id,))
            next_status = "in_progress"  # paying the vendor does not by itself fulfil the order
            detail = f"invoice {reference_id} marked paid"
        else:
            lease = connection.execute("SELECT next_due FROM leases WHERE id = ?", (reference_id,)).fetchone()
            next_due = _next_month(lease["next_due"])
            connection.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, reference_id))
            next_status = "resolved"
            detail = f"lease {reference_id} next_due moved to {next_due}"
        entry = _append_note(
            connection, ticket_id, "human",
            f"Payment of {amount} approved by {approver} from checking on {today}; {detail}; "
            f"balance now {new_balance}.",
        )
        connection.execute("UPDATE tickets SET status = ? WHERE id = ?", (next_status, ticket_id))
    return {
        "payment_made": True,
        "payment_id": cursor.lastrowid,
        "ticket_id": ticket_id,
        "kind": kind,
        "reference_id": reference_id,
        "amount": amount,
        "approved_by": approver,
        "balance": new_balance,
        "ticket_status": next_status,
        "entry": entry,
    }


@mcp.tool()
def resolve_ticket(ticket_id: int, resolved_by: str, resolution: str) -> dict[str, Any]:
    """Let a human close a ticket with a written resolution; agents cannot call this.

    Refuses tickets that are already resolved or still awaiting a payment approval, so a human
    must approve or reject the money first.
    """
    person = resolved_by.strip()
    outcome = resolution.strip()
    if not person or len(person) > 80:
        raise ValueError("resolved_by must be 1 to 80 characters naming the human.")
    if not outcome or len(outcome) > 900:
        raise ValueError("A resolution must contain 1 to 900 characters.")
    with _database(read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket = _ticket(connection, ticket_id)
        if ticket["status"] == "resolved":
            raise ValueError(f"Ticket {ticket_id} is already resolved.")
        if ticket["status"] == "awaiting_human_approval":
            raise ValueError(f"Ticket {ticket_id} is waiting on a payment approval; decide that first.")
        entry = _append_note(connection, ticket_id, "human", f"Resolved by {person}: {outcome}")
        connection.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
    return {"ticket_id": ticket_id, "status": "resolved", "resolved_by": person, "entry": entry}


@mcp.tool()
def reset_database() -> dict[str, Any]:
    """Restore the working database to the original values from data/campus_customs.db."""
    if not SOURCE_DATABASE_PATH.is_file():
        raise FileNotFoundError(f"Reset source database not found: {SOURCE_DATABASE_PATH}")
    source = sqlite3.connect(f"{SOURCE_DATABASE_PATH.as_uri()}?mode=ro", uri=True, timeout=5)
    target = sqlite3.connect(str(DATABASE_PATH), timeout=5)
    try:
        source.backup(target)
        target.commit()
        counts = {
            table: target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("tickets", "payments", "cash_accounts")
        }
        balance = target.execute("SELECT COALESCE(SUM(balance), 0) FROM cash_accounts").fetchone()[0]
    finally:
        source.close()
        target.close()
    return {"reset": True, "row_counts": counts, "checking_balance": float(balance)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
