"""Bounded, fully connected delegation across the five Campus Customs roles."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic_ai import UsageLimits

from backend.agents.accounting import create as create_accounting
from backend.agents.boss import create as create_boss
from backend.agents.context import AgentContext, TicketLoopState
from backend.agents.customer_service import create as create_customer_service
from backend.agents.facilities import create as create_facilities
from backend.agents.factory import usage_limits_for
from backend.agents.inventory import create as create_inventory
from backend.audit import append_event
from backend.mcp_client import MCPGateway
from backend.models import AgentReport, AgentRole, RunRequest, TeamRunResult, TicketRunResult


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "backend" / "prompts"
MAX_DELEGATIONS_PER_TICKET = 4
MAX_TICKETS_PER_RUN = 3
MAX_DELEGATION_TASK_CHARS = 1500


class AgentTeam:
    """One shared-model, five-agent team with per-ticket loop and tool limits."""

    def __init__(self, model: Any):
        self.agents = {
            "boss": create_boss(model),
            "inventory": create_inventory(model),
            "accounting": create_accounting(model),
            "facilities": create_facilities(model),
            "customer_service": create_customer_service(model),
        }
        self._prompt_hashes = {
            role: sha256((PROMPTS_DIR / f"{role}.md").read_bytes()).hexdigest()
            for role in self.agents
        }

    async def _run_agent(
        self,
        *,
        role: AgentRole,
        task: str,
        gateway: MCPGateway,
        state: TicketLoopState,
    ) -> AgentReport:
        if role in state.visited_roles:
            raise RuntimeError(f"Agent {role} already ran for ticket {state.ticket_id}.")
        state.visited_roles.add(role)
        state.visited_order.append(role)
        state.active_roles.append(role)
        append_event({
            "kind": "agent_step_start",
            "run_id": state.run_id,
            "ticket_id": state.ticket_id,
            "agent": role,
            "step": len(state.visited_order),
            "task": task[:MAX_DELEGATION_TASK_CHARS],
            "prompt_sha256": self._prompt_hashes[role],
        })
        deps = AgentContext(role=role, ticket_id=state.ticket_id, gateway=gateway, team=self, state=state)
        try:
            limits = usage_limits_for(role)
            result = await self.agents[role].run(
                task,
                deps=deps,
                usage_limits=UsageLimits(
                    request_limit=limits.request_limit,
                    tool_calls_limit=limits.tool_calls_limit,
                    total_tokens_limit=limits.total_tokens_limit,
                ),
            )
            report: AgentReport = result.output
            reported_id = report.ticket_id
            if reported_id not in (None, state.ticket_id):
                raise ValueError(f"Agent {role} returned report for a different ticket.")
            if reported_id is None:
                report = report.model_copy(update={"ticket_id": state.ticket_id})
            usage = result.usage()
            append_event({
                "kind": "agent_step_finish",
                "run_id": state.run_id,
                "ticket_id": state.ticket_id,
                "agent": role,
                "step": len(state.visited_order),
                "report": report.model_dump(mode="json"),
                "usage": {
                    field: getattr(usage, field, None)
                    for field in ("requests", "tool_calls", "input_tokens", "output_tokens", "total_tokens")
                },
                "mcp_calls_so_far": state.mcp_call_count,
                "delegations_so_far": state.delegation_count,
            })
            return report
        except Exception as exc:
            append_event({
                "kind": "agent_step_error",
                "run_id": state.run_id,
                "ticket_id": state.ticket_id,
                "agent": role,
                "step": len(state.visited_order),
                "error_type": type(exc).__name__,
                "mcp_calls_so_far": state.mcp_call_count,
                "delegations_so_far": state.delegation_count,
            })
            raise
        finally:
            if state.active_roles and state.active_roles[-1] == role:
                state.active_roles.pop()

    async def delegate(
        self,
        source: AgentContext,
        *,
        role: AgentRole,
        task: str,
    ) -> AgentReport:
        """Permit any unused role while blocking self-delegation, cycles, and excess."""
        allowed = (
            role != source.role
            and role in self.agents
            and role not in source.state.visited_roles
            and role not in source.state.active_roles
            and source.state.delegation_count < MAX_DELEGATIONS_PER_TICKET
            and len(task.strip()) > 0
            and len(task) <= MAX_DELEGATION_TASK_CHARS
        )
        if not allowed:
            append_event({
                "kind": "delegation_rejected",
                "run_id": source.state.run_id,
                "ticket_id": source.ticket_id,
                "from_agent": source.role,
                "to_agent": role,
                "task": task[:MAX_DELEGATION_TASK_CHARS],
                "reason": "self, cycle, repeated role, empty/oversized task, or delegation cap",
                "delegations_so_far": source.state.delegation_count,
            })
            raise ValueError("Delegation is blocked by this ticket's role-use or loop limits.")
        source.state.delegation_count += 1
        append_event({
            "kind": "delegation_start",
            "run_id": source.state.run_id,
            "ticket_id": source.ticket_id,
            "from_agent": source.role,
            "to_agent": role,
            "task": task,
            "delegation_number": source.state.delegation_count,
        })
        report = await self._run_agent(role=role, task=task, gateway=source.gateway, state=source.state)
        append_event({
            "kind": "delegation_finish",
            "run_id": source.state.run_id,
            "ticket_id": source.ticket_id,
            "from_agent": source.role,
            "to_agent": role,
            "delegation_number": source.state.delegation_count,
            "report": report.model_dump(mode="json"),
        })
        return report

    async def run(self, request: RunRequest, gateway: MCPGateway) -> TeamRunResult:
        """Triage open work through MCP, then run the Boss loop once per selected ticket."""
        run_id = str(uuid4())
        append_event({
            "kind": "team_run_start",
            "run_id": run_id,
            "ticket_filter": request.ticket_id,
            "max_tickets": request.max_tickets,
            "model": "gpt-6-luna",
        })
        open_tickets = await gateway.call(
            role="boss", ticket_id=None, tool_name="list_open_tickets", arguments={}, run_id=run_id,
        )
        if not isinstance(open_tickets, list):
            raise RuntimeError("MCP list_open_tickets returned an unexpected value.")
        candidates = [item for item in open_tickets if isinstance(item, dict) and "id" in item]
        if request.ticket_id is not None:
            candidates = [item for item in candidates if item["id"] == request.ticket_id]
            if not candidates:
                raise LookupError(f"Ticket {request.ticket_id} is not currently open in the working database.")
        selected = candidates[: min(request.max_tickets, MAX_TICKETS_PER_RUN)]
        skipped = [int(item["id"]) for item in candidates[len(selected):]]
        results: list[TicketRunResult] = []
        for ticket in selected:
            ticket_id = int(ticket["id"])
            # The shared board lookup counts toward each selected ticket's MCP-call budget.
            state = TicketLoopState(ticket_id=ticket_id, run_id=run_id, mcp_call_count=1)
            task = (
                f"Handle open Campus Customs ticket {ticket_id}, which the MCP ticket board reports as open. "
                "First verify the complete ticket and linked facts with MCP. Delegate only focused "
                "work that is useful; reconcile the evidence, record a factual note when appropriate, and decide "
                "whether the Boss should update status. Do not send messages or make payments. Return an AgentReport."
            )
            append_event({
                "kind": "ticket_loop_start",
                "run_id": run_id,
                "ticket_id": ticket_id,
                "mcp_ticket_snapshot": ticket,
            })
            try:
                report = await self._run_agent(role="boss", task=task, gateway=gateway, state=state)
                results.append(TicketRunResult(
                    ticket_id=ticket_id,
                    report=report,
                    agents_used=list(state.visited_order),
                ))
                append_event({
                    "kind": "ticket_loop_finish",
                    "run_id": run_id,
                    "ticket_id": ticket_id,
                    "agents_used": state.visited_order,
                    "delegations": state.delegation_count,
                    "mcp_calls": state.mcp_call_count,
                    "report": report.model_dump(mode="json"),
                })
            except Exception as exc:
                append_event({
                    "kind": "ticket_loop_error",
                    "run_id": run_id,
                    "ticket_id": ticket_id,
                    "agents_used": state.visited_order,
                    "delegations": state.delegation_count,
                    "mcp_calls": state.mcp_call_count,
                    "error_type": type(exc).__name__,
                })
                raise
        result = TeamRunResult(run_id=run_id, tickets=results, skipped_ticket_ids=skipped)
        append_event({
            "kind": "team_run_finish",
            "run_id": run_id,
            "ticket_ids": [item.ticket_id for item in results],
            "skipped_ticket_ids": skipped,
        })
        return result
