from typing import TypedDict

from langgraph.graph import MessagesState


#  ================================================
# states 
class Context(TypedDict):
    """
    Defines the context for the agent.
    """
    model: str
    agent_id: str


class InputState(TypedDict):
    """
    Defines the input state for the agent.
    """
    task: str

class State(MessagesState):
    """
    Defines the state for the agent.
    """
    task: str