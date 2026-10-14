"""Shared dependency objects passed to each role's PydanticAI tool loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.models import AgentRole
from backend.mcp_client import MCPGateway

if TYPE_CHECKING:
    from backend.team import AgentTeam


@dataclass
class TicketLoopState:
    ticket_id: int
    run_id: str
    visited_roles: set[AgentRole] = field(default_factory=set)
    visited_order: list[AgentRole] = field(default_factory=list)
    active_roles: list[AgentRole] = field(default_factory=list)
    delegation_count: int = 0
    mcp_call_count: int = 0


@dataclass
class AgentContext:
    role: AgentRole
    ticket_id: int
    gateway: MCPGateway
    team: "AgentTeam"
    state: TicketLoopState
