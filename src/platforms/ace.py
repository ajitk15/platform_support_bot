from langchain_core.messages import AIMessage
from ..state import AgentState

async def ace_agent(state: AgentState):
    return {"messages": [AIMessage(content="[ACE Agent] IBM ACE integration is coming soon. I cannot check flows currently.")]}
