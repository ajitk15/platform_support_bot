from langchain_core.messages import SystemMessage
from langgraph.graph import END
from ..state import AgentState

async def splunk_agent(state: AgentState, model, splunk_tools_list):
    messages = state["messages"]
    system_instruction = "You are a Splunk expert. Use the provided tools to search logs and inspect indexes."
    model_with_tools = model.bind_tools(splunk_tools_list)
    msgs = [SystemMessage(content=system_instruction)] + list(messages)
    response = await model_with_tools.ainvoke(msgs)
    return {"messages": [response], "sender": "splunk_agent"} # Track sender

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END
