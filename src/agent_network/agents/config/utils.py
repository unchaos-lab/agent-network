from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    # ANTHROPIC_API_KEY must be set in the environment variables
    provider, model = fully_specified_name.split("/", maxsplit=1)
    return init_chat_model(model, model_provider=provider)

def create_human_message(message: str) -> HumanMessage:
    return HumanMessage(content=message)

def create_system_message(message: str) -> SystemMessage:
    return SystemMessage(content=message)

def create_ai_message(message: str) -> AIMessage:
    return AIMessage(content=message)