"""Inventory agent: verifies quantity, exact SKU/size, vendors, and lead times."""

from backend.agents.factory import build_agent
from backend.models import AgentRole

ROLE: AgentRole = "inventory"


def create(model):
    return build_agent(ROLE, model)
