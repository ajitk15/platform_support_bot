from langchain_core.messages import AIMessage
from ..state import AgentState

async def apigee_agent(state: AgentState):
    return {"messages": [AIMessage(content="[Apigee Agent] Apigee integration is coming soon. I cannot check proxies currently.")]}
