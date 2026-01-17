from langchain_core.messages import SystemMessage, HumanMessage
from .state import AgentState

async def platform_router(state: AgentState, model):
    """
    Analyzes the query to route to the correct platform agent.
    Valid platforms: MQ, Splunk, Redis, ACE, Apigee, General.
    """
    messages = state["messages"]
    last_user_msg = messages[-1].content
    
    # Prompt for the router
    router_prompt = (
        "You are an intelligent router. Your goal is to direct the user's query to the correct platform specialist.\n"
        "The available platforms are:\n"
        "1. MQ (IBM MQ, queues, channels, dspmq, runmqsc)\n"
        "2. Splunk (logs, search, indexes)\n"
        "3. Redis (cache, keys, memory)\n"
        "4. ACE (IBM App Connect Enterprise, flows, integration servers)\n"
        "5. Apigee (API proxies, traffic, gateways)\n\n"
        "Analyse the user's message and output only the name of the platform (MQ, Splunk, Redis, ACE, Apigee, or General).\n"
        "If the user does not specify a platform, infer it from keywords (e.g., 'queue' -> MQ, 'log' -> Splunk, 'cache' -> Redis).\n"
        "If the query is a greeting, 'help', or unrelated to the supported platforms, output 'General'.\n"
        "If you are absolutely unsure, default to 'Splunk'."
    )
    
    # We ask the LLM to classify. 
    response = await model.ainvoke([SystemMessage(content=router_prompt), HumanMessage(content=last_user_msg)])
    choice = response.content.strip().lower()
    
    # Normalize output
    if "mq" in choice: return {"platform": "mq"}
    if "redis" in choice: return {"platform": "redis"}
    if "ace" in choice: return {"platform": "ace"}
    if "apigee" in choice: return {"platform": "apigee"}
    if "general" in choice: return {"platform": "general"}
    
    # Default
    return {"platform": "splunk"}
