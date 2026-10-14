"""Boss agent: owns triage, delegation, and the final ticket state."""

from backend.agents.factory import build_agent
from backend.models import AgentRole

ROLE: AgentRole = "boss"


def create(model):
    return build_agent(ROLE, model)
