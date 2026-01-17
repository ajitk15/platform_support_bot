from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from .state import AgentState
from .router import platform_router
from .platforms.mq import mq_agent, route_mq_tools
from .platforms.splunk import splunk_agent, should_continue
from .platforms.redis import redis_agent, redis_search
from .platforms.ace import ace_agent
from .platforms.apigee import apigee_agent
from .platforms.general import general_agent

def route_tool_output(state: AgentState) -> str:
    """
    Routes tool output back to the agent that called it.
    Uses 'sender' field in state.
    """
    return state.get("sender", "splunk_agent")

async def create_graph(tools_map, model):
    mq_tools_list = tools_map["mq"]
    splunk_tools_list = tools_map["splunk"]

    workflow = StateGraph(AgentState)

    # Add Nodes
    # NOTE: Using partial to pass existing model/tools while keeping the signature correct for LangGraph
    from functools import partial
    
    workflow.add_node("platform_router", partial(platform_router, model=model))
    
    workflow.add_node("mq_agent", partial(mq_agent, model=model, mq_tools_list=mq_tools_list, splunk_tools_list=splunk_tools_list))
    workflow.add_node("splunk_agent", partial(splunk_agent, model=model, splunk_tools_list=splunk_tools_list))
    workflow.add_node("redis_agent", partial(redis_agent, model=model))
    
    workflow.add_node("ace_agent", ace_agent)
    workflow.add_node("apigee_agent", apigee_agent)
    workflow.add_node("general_agent", general_agent)
    
    # Tool Nodes
    workflow.add_node("mq_tools", ToolNode(mq_tools_list))
    workflow.add_node("splunk_tools", ToolNode(splunk_tools_list)) 
    workflow.add_node("redis_tools", ToolNode([redis_search])) 

    # Edges
    # Start -> Router
    workflow.add_edge(START, "platform_router")
    
    # Router -> Agent (Conditional)
    workflow.add_conditional_edges(
        "platform_router",
        lambda state: f"{state['platform']}_agent", 
        {
            "mq_agent": "mq_agent",
            "splunk_agent": "splunk_agent",
            "redis_agent": "redis_agent",
            "ace_agent": "ace_agent",
            "apigee_agent": "apigee_agent",
            "general_agent": "general_agent"
        }
    )

    # Agents -> Tools or End
    
    # MQ (Updated with Smart Routing)
    workflow.add_conditional_edges(
        "mq_agent", 
        lambda state: route_mq_tools(state, mq_tools_list), 
        {
            "mq_tools": "mq_tools", 
            "splunk_tools": "splunk_tools", # Route to SHARED splunk node
            END: END
        }
    )
    
    # Splunk
    workflow.add_conditional_edges("splunk_agent", should_continue, {"tools": "splunk_tools", END: END})
    
    # Redis
    workflow.add_conditional_edges("redis_agent", should_continue, {"tools": "redis_tools", END: END})
    workflow.add_edge("redis_tools", "redis_agent")
    
    # Tool Return Routing (Dynamic)
    workflow.add_conditional_edges("mq_tools", route_tool_output, {"mq_agent": "mq_agent"})
    workflow.add_conditional_edges("splunk_tools", route_tool_output, 
                                   {"mq_agent": "mq_agent", "splunk_agent": "splunk_agent"})

    # Placeholders just end
    workflow.add_edge("ace_agent", END)
    workflow.add_edge("apigee_agent", END)
    workflow.add_edge("general_agent", END)

    return workflow.compile()
