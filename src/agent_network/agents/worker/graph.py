from typing import TypedDict
from langgraph.graph import MessagesState
from langgraph.runtime import Runtime
from typing import Any, Dict, cast
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from logging import getLogger

from langchain_core.messages import BaseMessage, AIMessage

from agent_network.agents.worker.shemas import Context, State, InputState
from agent_network.agents.config.utils import load_chat_model, create_human_message, create_system_message, create_ai_message
from agent_network.agents.worker.prompts import SYSTEM_PROMPT 

logger = getLogger(__name__)

# ================================================
# nodes 

def setup(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    """Initial setup node to pass the task to the state."""

    messages: list[BaseMessage] = [create_system_message(SYSTEM_PROMPT),
                                   create_human_message(f"here is the user's task: {state['task']}")]
    return {"messages": messages}

def work(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    logger.info(f"Agent received task: {state['task']}")

    model = load_chat_model(runtime.context['model'])

    response = cast(AIMessage, model.invoke(state["messages"]))
    return {"messages": [response]}

# ================================================
# build graph

# Define a new graph
builder = StateGraph(input_schema=InputState, state_schema=State, context_schema=Context)

# Add nodes to the graph
builder.add_node(setup)
builder.add_node(work)

# Add edges between nodes
builder.set_entry_point("setup")
builder.add_edge("setup", "work")
builder.set_finish_point("work")