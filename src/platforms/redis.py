from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import END
from ..state import AgentState

@tool
def redis_search(query: str) -> str:
    """Search the latest logs in Redis. Use this when user asks for 'latest logs' or 'recent logs' in Redis."""
    return f"[Redis] Implementation pending. Mock result for query: {query}"

async def redis_agent(state: AgentState, model):
    messages = state["messages"]
    system_instruction = "You are a Redis expert. Use the provided tools to check cache status."
    model_with_tools = model.bind_tools([redis_search]) # Bind mock tool
    msgs = [SystemMessage(content=system_instruction)] + list(messages)
    response = await model_with_tools.ainvoke(msgs)
    return {"messages": [response], "sender": "redis_agent"} # Track sender

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END
