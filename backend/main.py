"""HTTP backend for the Campus Customs agent team and its React dashboard.

Start from this folder with:  uvicorn main:app --reload --port 8000
(or from the project root with:  python -m uvicorn backend.main:app --port 8000)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
from typing import Any, AsyncIterator, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    # Lets `backend.*` imports resolve when uvicorn is started from inside backend/.
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.audit import append_event, read_recent_events
from backend.models import ApprovalRequest, ResolveRequest, RunRequest, TeamRunResult
from backend.mcp_client import connected_mcp
from backend.team import AgentTeam


MODEL_ID = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
DASHBOARD_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (3000, 4173, 5173)  # 5173 = `npm run dev`, 4173 = `npm run preview`
]


def _load_environment() -> None:
    """Read .env from the project, then up to two parent folders (e.g. the course root)."""
    for folder in (PROJECT_ROOT, *PROJECT_ROOT.parents[:2]):
        load_dotenv(folder / ".env", override=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the Portkey credential at runtime; never persist or log it."""
    _load_environment()
    portkey_key = os.getenv("PORTKEY_API_KEY")
    if not portkey_key:
        raise RuntimeError("PORTKEY_API_KEY must be set in the environment before starting the agent API.")
    http_client = httpx.AsyncClient(
        headers={"x-portkey-api-key": portkey_key},
        timeout=httpx.Timeout(45.0, connect=10.0),
    )
    try:
        provider = OpenAIProvider(
            base_url=PORTKEY_BASE_URL,
            api_key=portkey_key,
            http_client=http_client,
        )
        model = OpenAIChatModel(MODEL_ID, provider=provider)
        app.state.agent_team = AgentTeam(model)
        # One long-lived MCP connection serves the dashboard's frequent read calls. Starting a new
        # server process for every poll is slow (seconds each) and leaves stray processes behind.
        async with connected_mcp() as human_gateway:
            app.state.human_gateway = human_gateway
            yield
    finally:
        await http_client.aclose()


app = FastAPI(
    title="Campus Customs Agent Team",
    description="Bounded Boss, Inventory, Accounting, Facilities, and Customer Service agent workflow.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DASHBOARD_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _root_cause(exc: BaseException) -> BaseException:
    """The MCP stdio task group wraps errors in an ExceptionGroup; unwrap single-error groups."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return exc


async def _human_tool(tool_name: str, arguments: dict[str, Any] | None = None, ticket_id: int | None = None) -> Any:
    """Call a human/dashboard MCP tool; the backend never touches SQLite itself."""
    call = dict(role="human", ticket_id=ticket_id, tool_name=tool_name, arguments=arguments or {})
    try:
        return await app.state.human_gateway.call(**call)
    except (RuntimeError, ValueError, PermissionError):
        raise  # a real tool answer (for example "not awaiting approval"), not a connection problem
    except Exception:
        # The shared connection broke (for example its server process died): fall back to a fresh one.
        try:
            async with connected_mcp() as gateway:
                return await gateway.call(**call)
        except BaseExceptionGroup as group:
            raise _root_cause(group) from None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": MODEL_ID}


@app.get("/tickets")
async def list_tickets() -> list[dict[str, Any]]:
    """All tickets, each marked `open` or `resolved` (`status` keeps the exact stored workflow state)."""
    tickets = await _human_tool("list_all_tickets")
    return [{**ticket, "state": "resolved" if ticket["status"] == "resolved" else "open"} for ticket in tickets]


async def _run(payload: RunRequest, request: Request) -> TeamRunResult:
    try:
        async with connected_mcp() as gateway:
            return await request.app.state.agent_team.run(payload, gateway)
    except Exception as exc:
        cause = _root_cause(exc)
        if isinstance(cause, LookupError):
            known = {item["id"] for item in await _human_tool("list_all_tickets")}
            code = 409 if payload.ticket_id in known else 404
            raise HTTPException(status_code=code, detail=str(cause)) from cause
        if isinstance(cause, (PermissionError, ValueError)):
            raise HTTPException(status_code=400, detail=str(cause)) from cause
        raise HTTPException(status_code=502, detail=f"Agent run failed: {type(cause).__name__}") from cause


@app.post("/tickets/{ticket_id}/run", response_model=TeamRunResult)
async def run_ticket(ticket_id: int, request: Request) -> TeamRunResult:
    """Run the agent team on one open ticket."""
    return await _run(RunRequest(ticket_id=ticket_id, max_tickets=1), request)


@app.post("/run", response_model=TeamRunResult)
async def run_team(payload: RunRequest, request: Request) -> TeamRunResult:
    """Run one selected open ticket or a capped batch from the MCP board."""
    return await _run(payload, request)


@app.get("/events")
async def recent_events(
    limit: int = Query(default=50, ge=1, le=200),
    ticket_id: Optional[int] = Query(default=None, ge=1),
) -> dict[str, Any]:
    """Newest audit events (oldest first): what each agent said and which tools it used."""
    return {"events": read_recent_events(limit=limit, ticket_id=ticket_id)}


@app.post("/tickets/{ticket_id}/approve")
async def approve_payment(ticket_id: int, payload: ApprovalRequest) -> Any:
    """Human-click approval: the only route that moves cash (agents just prepare the request)."""
    try:
        result = await _human_tool(
            "approve_payment",
            {"ticket_id": ticket_id, "approved_by": payload.approved_by},
            ticket_id=ticket_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    append_event({"kind": "human_payment_decision", "actor": "human", "ticket_id": ticket_id, "result": result})
    if not result.get("payment_made"):
        return JSONResponse(status_code=409, content=result)
    return result


@app.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, payload: ResolveRequest) -> dict[str, Any]:
    """Human closes a ticket with a written resolution; agents can never resolve a ticket themselves."""
    try:
        result = await _human_tool(
            "resolve_ticket",
            {"ticket_id": ticket_id, "resolved_by": payload.resolved_by, "resolution": payload.resolution},
            ticket_id=ticket_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    append_event({
        "kind": "human_resolution", "actor": "human", "ticket_id": ticket_id,
        "resolved_by": payload.resolved_by, "resolution": payload.resolution,
    })
    return result


@app.get("/balance")
async def checking_balance() -> dict[str, Any]:
    """Current checking balance from cash_accounts."""
    return await _human_tool("get_checking_balance")


@app.post("/reset")
async def reset_database() -> dict[str, Any]:
    """Restore the working database to its original values for a fresh run."""
    result = await _human_tool("reset_database")
    append_event({"kind": "database_reset", "actor": "human", "result": result})
    return result
