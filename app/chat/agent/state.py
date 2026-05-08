from langgraph.graph import MessagesState


class SalonState(MessagesState):
    flow: str | None
    employee_id: int | None
    service_id: int | None
    preferred_employee_id: int | None
