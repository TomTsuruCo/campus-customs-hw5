"""Common constrained tool-loop setup for each of the five agent roles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic_ai import Agent, RunContext, UsageLimits

from backend.agents.context import AgentContext
from backend.mcp_client import ROLE_TOOLS
from backend.models import AgentReport, AgentRole


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "backend" / "prompts"
ALL_TOOL_NAMES = Literal[
    "list_open_tickets",
    "check_inventory",
    "get_ticket_details",
    "get_shop_financial_status",
    "list_vendors_with_shipping_status",
    "append_ticket_note",
    "save_customer_draft",
    "request_payment_approval",
    "update_ticket_status",
]


def build_agent(role: AgentRole, model: Any) -> Agent[AgentContext, AgentReport]:
    """Build one agent using its own prompt and a small, role-gated tool surface."""
    prompt = (PROMPTS_DIR / f"{role}.md").read_text(encoding="utf-8")
    agent = Agent(
        model,
        deps_type=AgentContext,
        output_type=AgentReport,
        instructions=prompt,
        model_settings={"openai_reasoning_effort": "none"},
        name=f"campus_customs_{role}",
        retries=1,
        output_retries=2,
    )

    @agent.tool
    async def call_mcp_tool(
        ctx: RunContext[AgentContext],
        tool_name: ALL_TOOL_NAMES,
        arguments: dict[str, Any],
    ) -> Any:
        """Call one named shared MCP tool with its documented JSON arguments."""
        if tool_name not in ROLE_TOOLS[role]:
            return {"error": f"{role} may not use MCP tool {tool_name}. Ask another role via delegate_to_agent."}
        if ctx.deps.state.mcp_call_count >= 20:
            raise RuntimeError("The per-ticket MCP call limit (20) has been reached.")
        ctx.deps.state.mcp_call_count += 1
        try:
            return await ctx.deps.gateway.call(
                role=role,
                ticket_id=ctx.deps.ticket_id,
                tool_name=tool_name,
                arguments=arguments,
                run_id=ctx.deps.state.run_id,
            )
        except (PermissionError, ValueError) as exc:
            # A refused call is reported back so the agent can adapt; the rule itself is unchanged.
            return {"error": str(exc)}
        except RuntimeError as exc:
            if "reported an error" not in str(exc):
                raise
            return {"error": str(exc)}

    @agent.tool
    async def delegate_to_agent(
        ctx: RunContext[AgentContext],
        role: AgentRole,
        task: str,
    ) -> str:
        """Delegate focused work to any other unused role, subject to loop caps."""
        try:
            report = await ctx.deps.team.delegate(ctx.deps, role=role, task=task)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        return report.model_dump_json()

    return agent


ROLE_USAGE_LIMITS = UsageLimits(
    request_limit=6,
    tool_calls_limit=8,
    total_tokens_limit=8000,
)
# The Boss re-reads its whole history, including each delegation report, on every request.
BOSS_USAGE_LIMITS = UsageLimits(
    request_limit=10,
    tool_calls_limit=12,
    total_tokens_limit=24000,
)


def usage_limits_for(role: AgentRole) -> UsageLimits:
    return BOSS_USAGE_LIMITS if role == "boss" else ROLE_USAGE_LIMITS
