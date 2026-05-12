from typing import Annotated, Any, NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware.types import OmitFromInput
from langgraph.managed import RemainingSteps


class SalonState(AgentState[Any]):
    """State for the salon agent (langchain.agents.create_agent + LangGraph checkpoint)."""

    remaining_steps: NotRequired[Annotated[RemainingSteps, OmitFromInput]]
    flow: NotRequired[str | None]
    employee_id: NotRequired[int | None]
    service_id: NotRequired[int | None]
    preferred_service_id: NotRequired[int | None]
    preferred_employee_id: NotRequired[int | None]
