"""Customer Service agent: prepares accurate, unsent customer drafts."""

from backend.agents.factory import build_agent
from backend.models import AgentRole

ROLE: AgentRole = "customer_service"


def create(model):
    return build_agent(ROLE, model)
