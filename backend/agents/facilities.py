"""Facilities agent: handles premises, leases, and rent-related ticket work."""

from backend.agents.factory import build_agent
from backend.models import AgentRole

ROLE: AgentRole = "facilities"


def create(model):
    return build_agent(ROLE, model)
