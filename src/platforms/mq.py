from langchain_core.messages import SystemMessage
from langgraph.graph import END
from ..state import AgentState

async def mq_agent(state: AgentState, model, mq_tools_list, splunk_tools_list):
    messages = state["messages"]
    system_instruction = (
        "You are an IBM MQ expert. Your goal is to diagnose MQ issues using a FALLBACK STRATEGY:\n"
        "1. PRIMARY: Use 'mq_tools' (dspmq, runmqsc) to check the live status of queue managers and queues.\n"
        "2. FALLBACK: If the MQ tools fail, return errors, or you cannot connect, you MUST search Splunk logs.\n"
        "   - Use 'splunk_tools' (search_splunk).\n"
        "   - CRITICAL: When using Splunk, ALWAYS filter by `index=ibmmq` to find relevant MQ logs.\n"
        "   - Example Splunk Query: `search index=ibmmq error OR fail | head 20`"
    )
    
    # Bind BOTH MQ and Splunk tools to allow fallback
    all_tools = mq_tools_list + splunk_tools_list
    model_with_tools = model.bind_tools(all_tools)
    
    msgs = [SystemMessage(content=system_instruction)] + list(messages)
    response = await model_with_tools.ainvoke(msgs)
    return {"messages": [response], "sender": "mq_agent"} # Track sender

def route_mq_tools(state: AgentState, mq_tools_list) -> str:
    """
    Routes MQ agent's tool calls to the appropriate node.
    - MQ tools -> mq_tools
    - Splunk tools -> splunk_tools
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Check the first tool call to decide destination
        tool_name = last_message.tool_calls[0]["name"]
        
        # Check if it's an MQ tool
        for t in mq_tools_list:
            if t.name == tool_name:
                return "mq_tools"
        
        # Otherwise assume it's Splunk (since we bound both)
        return "splunk_tools"
        
    return END
