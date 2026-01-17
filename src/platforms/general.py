from langchain_core.messages import AIMessage
from ..state import AgentState

async def general_agent(state: AgentState):
    msg = (
        "I can help with **IBM MQ**, **Splunk**, **Redis**, **ACE**, and **Apigee** issues. "
        "Please ask specifically about these platforms.\n\n"
        "Examples:\n"
        "- 'Show MQ queue status'\n"
        "- 'Search Splunk for errors'\n"
        "- 'Check Redis cache'"
    )
    return {"messages": [AIMessage(content=msg)]}
