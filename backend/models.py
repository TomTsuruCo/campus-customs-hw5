"""Validated data exchanged by the Campus Customs agent team."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AgentRole = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["in_progress", "blocked", "awaiting_human_approval", "resolved"]


class AgentReport(BaseModel):
    """Short, structured finding returned by an agent to its caller."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: int | None = None
    summary: str = Field(min_length=1, max_length=1200)
    findings: list[str] = Field(default_factory=list, max_length=12)
    recommendation: str = Field(default="", max_length=1200)
    recommended_status: TicketStatus | None = None
    human_action_required: bool = False


class RunRequest(BaseModel):
    """Optional ticket filter and batch limit for a bounded team run."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: int | None = Field(default=None, ge=1)
    max_tickets: int = Field(default=3, ge=1, le=3)


class ApprovalRequest(BaseModel):
    """Body of the human-click payment approval."""

    model_config = ConfigDict(extra="forbid")

    approved_by: str = Field(default="dashboard user", min_length=1, max_length=80)


class ResolveRequest(BaseModel):
    """Body of the human's close-the-ticket action."""

    model_config = ConfigDict(extra="forbid")

    resolved_by: str = Field(default="dashboard user", min_length=1, max_length=80)
    resolution: str = Field(min_length=1, max_length=900)


class TicketRunResult(BaseModel):
    ticket_id: int
    report: AgentReport
    agents_used: list[AgentRole]


class TeamRunResult(BaseModel):
    run_id: str
    tickets: list[TicketRunResult]
    skipped_ticket_ids: list[int] = Field(default_factory=list)

