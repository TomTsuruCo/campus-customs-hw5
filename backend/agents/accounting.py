"""Accounting agent: checks amounts, dates, cash, and human payment approval."""

from backend.agents.factory import build_agent
from backend.models import AgentRole

ROLE: AgentRole = "accounting"


def create(model):
    return build_agent(ROLE, model)
