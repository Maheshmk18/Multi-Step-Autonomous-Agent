import operator
from typing import Annotated, Any

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    request: str
    steps: int
    route: str
    task: str
    results: Annotated[list[dict[str, Any]], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    sources: Annotated[list[dict[str, str]], operator.add]
    agent_messages: list[dict[str, Any]]
    pending_action: dict[str, Any] | None
    approval_result: str
    final_answer: str
