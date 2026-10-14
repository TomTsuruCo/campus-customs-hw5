"""Managed MCP stdio client; this is the backend's only shop-data gateway."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.audit import append_event


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_PATH = PROJECT_ROOT / "mcp_server" / "server.py"

TOOL_SCHEMAS: dict[str, set[str]] = {
    "list_open_tickets": set(),
    "check_inventory": {"sku", "size"},
    "get_ticket_details": {"ticket_id"},
    "get_shop_financial_status": set(),
    "list_vendors_with_shipping_status": set(),
    "append_ticket_note": {"ticket_id", "note"},
    "save_customer_draft": {"ticket_id", "draft"},
    "request_payment_approval": {"ticket_id"},
    "update_ticket_status": {"ticket_id", "status"},
    # Human/dashboard tools (Problem 7); never granted to an agent role.
    "list_all_tickets": set(),
    "get_checking_balance": set(),
    "approve_payment": {"ticket_id", "approved_by"},
    "resolve_ticket": {"ticket_id", "resolved_by", "resolution"},
    "reset_database": set(),
}

ROLE_TOOLS: dict[str, set[str]] = {
    "boss": {
        "list_open_tickets", "get_ticket_details", "get_shop_financial_status",
        "append_ticket_note", "request_payment_approval", "update_ticket_status",
    },
    "inventory": {
        "check_inventory", "get_ticket_details", "list_vendors_with_shipping_status",
        "append_ticket_note",
    },
    "accounting": {
        "get_ticket_details", "get_shop_financial_status", "append_ticket_note",
    },
    "facilities": {
        "get_ticket_details", "get_shop_financial_status", "append_ticket_note",
    },
    "customer_service": {
        "get_ticket_details", "check_inventory", "append_ticket_note", "save_customer_draft",
    },
    # Acts only through the human-click API routes in backend/main.py.
    "human": {"list_all_tickets", "get_checking_balance", "approve_payment", "resolve_ticket", "reset_database"},
}


@asynccontextmanager
async def connected_mcp() -> AsyncIterator["MCPGateway"]:
    """Start the project's FastMCP server and yield a single initialized session."""
    if not SERVER_PATH.is_file():
        raise FileNotFoundError(f"MCP server not found: {SERVER_PATH}")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(PROJECT_ROOT),
        env={
            key: value
            for key, value in os.environ.items()
            if not key.upper().endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
        },
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield MCPGateway(session)


class MCPGateway:
    """Validate role permissions and ticket scope before calling shared MCP tools."""

    def __init__(self, session: ClientSession):
        self._session = session

    async def call(
        self,
        *,
        role: str,
        ticket_id: int | None,
        tool_name: str,
        arguments: dict[str, Any],
        run_id: str | None = None,
    ) -> Any:
        allowed = ROLE_TOOLS.get(role)
        if allowed is None or tool_name not in allowed:
            raise PermissionError(f"Role {role!r} cannot call MCP tool {tool_name!r}.")
        required = TOOL_SCHEMAS[tool_name]
        if set(arguments) != required:
            raise ValueError(f"{tool_name} expects exactly these arguments: {sorted(required)}")
        if "ticket_id" in arguments and ticket_id is not None and arguments["ticket_id"] != ticket_id:
            raise PermissionError("An agent may only read or update its currently assigned ticket.")
        if tool_name == "update_ticket_status" and role != "boss":
            raise PermissionError("Only the Boss may update ticket status.")
        if tool_name == "save_customer_draft" and role != "customer_service":
            raise PermissionError("Only Customer Service may save a customer draft.")
        if tool_name == "request_payment_approval" and role != "boss":
            raise PermissionError("Only the Boss may record a human payment-approval request.")

        actual_arguments = dict(arguments)
        if tool_name in {"append_ticket_note", "save_customer_draft", "request_payment_approval", "update_ticket_status"}:
            actual_arguments["actor"] = role
        # The dashboard polls these two read-only tools every few seconds; auditing them would bury real events.
        audited = not (role == "human" and tool_name in {"list_all_tickets", "get_checking_balance"})
        event = {
            "kind": "mcp_tool_start",
            "run_id": run_id,  # ties each tool call to the agent run that made it
            "agent": role,
            "ticket_id": ticket_id,
            "tool_name": tool_name,
            "arguments": actual_arguments,
        }
        log = append_event if audited else (lambda _event: None)
        log(event)
        try:
            result = await self._session.call_tool(tool_name, actual_arguments)
            if result.isError:
                output: Any = {"error": True, "content": [getattr(c, "text", "") for c in result.content]}
                log({**event, "kind": "mcp_tool_error", "output": output})
                raise RuntimeError(f"MCP tool {tool_name} reported an error: {output}")
            output = getattr(result, "structuredContent", None)
            if isinstance(output, dict) and set(output) == {"result"}:
                output = output["result"]
            if output is None:
                texts = [getattr(block, "text", "") for block in result.content]
                if len(texts) == 1:
                    try:
                        output = json.loads(texts[0])
                    except (json.JSONDecodeError, TypeError):
                        output = texts[0]
                else:
                    output = texts
            log({**event, "kind": "mcp_tool_result", "output": output})
            return output
        except Exception as exc:
            if not isinstance(exc, RuntimeError) or "reported an error" not in str(exc):
                log({**event, "kind": "mcp_tool_error", "error": f"{type(exc).__name__}: {exc}"})
            raise
