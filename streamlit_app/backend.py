"""
Backend Orchestration Module for Platform Support Bot.

This module implements a LangGraph-based multi-agent orchestration system
that routes queries to specialized platform agents (MQ, Splunk, Redis, ACE, Apigee).

Architecture:
    __start__ → platform_router → [mq_agent | splunk_agent | redis_agent | ace_agent | apigee_agent | general_agent] → __end__
    
    Tool Nodes:
    - mq_tools: Used by mq_agent
    - splunk_tools: Used by mq_agent AND splunk_agent (shared)
    - redis_tools: Used by redis_agent (placeholder)
"""

import os
import sys
import operator
from pathlib import Path
from typing import TypedDict, Annotated, Literal, List, Any
from functools import partial

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Load environment variables
load_dotenv(parent_dir / ".env")

# Import MCP connection manager and system prompts
from mcp_connection import MultiMCPSessionManager
from sys_prompt import get_platform_prompt


# ============================================
# STATE DEFINITION
# ============================================

class AgentState(TypedDict):
    """State shared across all agents in the graph."""
    messages: Annotated[list, operator.add]  # Conversation history
    platform: str                             # Current platform (mq, splunk, redis, etc.)
    sender: str                               # Last agent that called tools (for routing)


# ============================================
# LLM INITIALIZATION
# ============================================

def get_llm():
    """Get the LLM based on environment configuration."""
    llm_type = os.getenv("LLM_CONNECTION", "gemini").lower()
    
    if llm_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key)
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)


# ============================================
# PLACEHOLDER TOOLS
# ============================================

async def redis_search_placeholder(query: str) -> str:
    """Placeholder Redis search tool."""
    return f"🚧 Redis tools are under development. Query received: {query}"

redis_search_tool = StructuredTool.from_function(
    coroutine=redis_search_placeholder,
    name="redis_search",
    description="Search Redis cache (placeholder - under development)"
)


# ============================================
# PLATFORM ROUTER
# ============================================

async def platform_router(state: AgentState, model) -> dict:
    """
    Analyzes the query to route to the correct platform agent.
    Uses LLM to intelligently classify the query.
    """
    messages = state["messages"]
    last_user_msg = messages[-1].content if messages else ""
    
    # If platform is already specified (e.g. from UI selection), respect it
    if state.get("platform") and state["platform"] not in ["general", ""]:
        print(f"[ROUTER] Using pre-selected platform: {state['platform']}")
        return {"platform": state["platform"]}
    
    router_prompt = (
        "You are an intelligent router. Your goal is to direct the user's query to the correct platform specialist.\n"
        "The available platforms are:\n"
        "1. MQ (IBM MQ, queues, channels, dspmq, runmqsc, queue manager)\n"
        "2. Splunk (logs, search, indexes, SPL queries, monitoring)\n"
        "3. Redis (cache, keys, memory, key-value store)\n"
        "4. ACE (IBM App Connect Enterprise, flows, integration servers, ESB)\n"
        "5. Apigee (API proxies, traffic, gateways, API management)\n\n"
        "Analyse the user's message and output ONLY the name of the platform (MQ, Splunk, Redis, ACE, Apigee, or General).\n"
        "If the user does not specify a platform, infer it from keywords.\n"
        "If the query is a greeting, 'help', or unrelated to the supported platforms, output 'General'.\n"
        "If you are absolutely unsure, default to 'General'."
    )
    
    try:
        response = await model.ainvoke([
            SystemMessage(content=router_prompt), 
            HumanMessage(content=last_user_msg)
        ])
        choice = response.content.strip().lower()
        
        # Normalize output
        if "mq" in choice: 
            platform = "mq"
        elif "redis" in choice: 
            platform = "redis"
        elif "ace" in choice: 
            platform = "ace"
        elif "apigee" in choice: 
            platform = "apigee"
        elif "splunk" in choice: 
            platform = "splunk"
        else:
            platform = "general"
        
        print(f"[ROUTER] Routing to: {platform}_agent")
        return {"platform": platform}
        
    except Exception as e:
        print(f"[ROUTER] Error: {e}, defaulting to general")
        return {"platform": "general"}


# ============================================
# AGENT NODES
# ============================================

async def mq_agent(state: AgentState, model, mq_tools: list, splunk_tools: list) -> dict:
    """
    MQ Agent - Handles IBM MQ operations.
    Has access to both MQ tools AND Splunk tools for log correlation.
    """
    print("[MQ_AGENT] Processing query...")
    
    # Combine tools (MQ tools + Splunk tools for correlation)
    all_tools = mq_tools + splunk_tools
    system_prompt = get_platform_prompt("mq", all_tools)
    
    # Bind tools to LLM
    llm_with_tools = model.bind_tools(all_tools)
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = await llm_with_tools.ainvoke(messages)
        return {
            "messages": [response],
            "sender": "mq_agent"
        }
    except Exception as e:
        print(f"[MQ_AGENT] Error: {e}")
        error_msg = AIMessage(content=f"MQ Agent encountered an error: {str(e)}")
        return {"messages": [error_msg], "sender": "mq_agent"}


async def splunk_agent(state: AgentState, model, splunk_tools: list) -> dict:
    """
    Splunk Agent - Handles Splunk log analysis queries.
    """
    print("[SPLUNK_AGENT] Processing query...")
    
    system_prompt = get_platform_prompt("splunk", splunk_tools)
    
    # Bind tools to LLM
    llm_with_tools = model.bind_tools(splunk_tools)
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = await llm_with_tools.ainvoke(messages)
        return {
            "messages": [response],
            "sender": "splunk_agent"
        }
    except Exception as e:
        print(f"[SPLUNK_AGENT] Error: {e}")
        error_msg = AIMessage(content=f"Splunk Agent encountered an error: {str(e)}")
        return {"messages": [error_msg], "sender": "splunk_agent"}


async def redis_agent(state: AgentState, model, redis_tools: list) -> dict:
    """
    Redis Agent - Handles Redis cache operations (placeholder).
    """
    print("[REDIS_AGENT] Processing query...")
    
    system_prompt = get_platform_prompt("redis", redis_tools)
    
    # Bind tools to LLM
    llm_with_tools = model.bind_tools(redis_tools)
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = await llm_with_tools.ainvoke(messages)
        return {
            "messages": [response],
            "sender": "redis_agent"
        }
    except Exception as e:
        print(f"[REDIS_AGENT] Error: {e}")
        error_msg = AIMessage(content=f"Redis Agent encountered an error: {str(e)}")
        return {"messages": [error_msg], "sender": "redis_agent"}


async def ace_agent(state: AgentState, model) -> dict:
    """
    ACE Agent - Handles IBM App Connect Enterprise queries (placeholder).
    """
    print("[ACE_AGENT] Processing query...")
    
    system_prompt = get_platform_prompt("ace", [])
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = await model.ainvoke(messages)
        return {
            "messages": [response],
            "sender": "ace_agent"
        }
    except Exception as e:
        print(f"[ACE_AGENT] Error: {e}")
        error_msg = AIMessage(content=f"ACE Agent encountered an error: {str(e)}")
        return {"messages": [error_msg], "sender": "ace_agent"}


async def apigee_agent(state: AgentState, model) -> dict:
    """
    Apigee Agent - Handles Apigee API gateway queries (placeholder).
    """
    print("[APIGEE_AGENT] Processing query...")
    
    system_prompt = get_platform_prompt("apigee", [])
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = await model.ainvoke(messages)
        return {
            "messages": [response],
            "sender": "apigee_agent"
        }
    except Exception as e:
        print(f"[APIGEE_AGENT] Error: {e}")
        error_msg = AIMessage(content=f"Apigee Agent encountered an error: {str(e)}")
        return {"messages": [error_msg], "sender": "apigee_agent"}


async def general_agent(state: AgentState, model) -> dict:
    """
    General Agent - Handles general queries and platform guidance.
    """
    print("[GENERAL_AGENT] Processing query...")
    
    system_prompt = get_platform_prompt("general", [])
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = await model.ainvoke(messages)
        return {
            "messages": [response],
            "sender": "general_agent"
        }
    except Exception as e:
        print(f"[GENERAL_AGENT] Error: {e}")
        error_msg = AIMessage(content=f"General Agent encountered an error: {str(e)}")
        return {"messages": [error_msg], "sender": "general_agent"}


# ============================================
# ROUTING FUNCTIONS
# ============================================

def route_to_agent(state: AgentState) -> str:
    """Route from platform_router to the appropriate agent."""
    platform = state.get("platform", "general")
    return f"{platform}_agent"


def should_continue_mq(state: AgentState, mq_tools: list, splunk_tools: list) -> str:
    """Determine if MQ agent should call tools or end."""
    messages = state.get("messages", [])
    if not messages:
        return END
    
    last_message = messages[-1]
    
    # Check if the last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        # Determine which tool node to use based on tool name
        tool_names = [tc['name'] for tc in last_message.tool_calls]
        mq_tool_names = [t.name for t in mq_tools]
        splunk_tool_names = [t.name for t in splunk_tools]
        
        # Check if any called tool is an MQ tool
        if any(name in mq_tool_names for name in tool_names):
            return "mq_tools"
        # Check if any called tool is a Splunk tool
        elif any(name in splunk_tool_names for name in tool_names):
            return "splunk_tools"
    
    return END


def should_continue_splunk(state: AgentState) -> str:
    """Determine if Splunk agent should call tools or end."""
    messages = state.get("messages", [])
    if not messages:
        return END
    
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "splunk_tools"
    
    return END


def should_continue_redis(state: AgentState) -> str:
    """Determine if Redis agent should call tools or end."""
    messages = state.get("messages", [])
    if not messages:
        return END
    
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "redis_tools"
    
    return END


def route_tool_output(state: AgentState) -> str:
    """Route tool output back to the calling agent."""
    return state.get("sender", "general_agent")


# ============================================
# GRAPH CONSTRUCTION
# ============================================

async def create_graph(tools_map: dict, model):
    """
    Create the LangGraph workflow with all agents and tool nodes.
    
    Args:
        tools_map: Dictionary with 'mq' and 'splunk' tool lists
        model: The LLM to use for agents
    
    Returns:
        Compiled LangGraph workflow
    """
    mq_tools = tools_map.get("mq", [])
    splunk_tools = tools_map.get("splunk", [])
    redis_tools = [redis_search_tool]  # Placeholder
    
    workflow = StateGraph(AgentState)
    
    # ==================
    # Add Agent Nodes
    # ==================
    workflow.add_node("platform_router", partial(platform_router, model=model))
    workflow.add_node("mq_agent", partial(mq_agent, model=model, mq_tools=mq_tools, splunk_tools=splunk_tools))
    workflow.add_node("splunk_agent", partial(splunk_agent, model=model, splunk_tools=splunk_tools))
    workflow.add_node("redis_agent", partial(redis_agent, model=model, redis_tools=redis_tools))
    workflow.add_node("ace_agent", partial(ace_agent, model=model))
    workflow.add_node("apigee_agent", partial(apigee_agent, model=model))
    workflow.add_node("general_agent", partial(general_agent, model=model))
    
    # ==================
    # Add Tool Nodes
    # ==================
    if mq_tools:
        workflow.add_node("mq_tools", ToolNode(mq_tools))
    if splunk_tools:
        workflow.add_node("splunk_tools", ToolNode(splunk_tools))
    workflow.add_node("redis_tools", ToolNode(redis_tools))
    
    # ==================
    # Define Edges
    # ==================
    
    # Start -> Router
    workflow.add_edge(START, "platform_router")
    
    # Router -> Agent (conditional)
    workflow.add_conditional_edges(
        "platform_router",
        route_to_agent,
        {
            "mq_agent": "mq_agent",
            "splunk_agent": "splunk_agent",
            "redis_agent": "redis_agent",
            "ace_agent": "ace_agent",
            "apigee_agent": "apigee_agent",
            "general_agent": "general_agent",
        }
    )
    
    # MQ Agent -> Tools or End
    if mq_tools or splunk_tools:
        workflow.add_conditional_edges(
            "mq_agent",
            partial(should_continue_mq, mq_tools=mq_tools, splunk_tools=splunk_tools),
            {
                "mq_tools": "mq_tools",
                "splunk_tools": "splunk_tools",
                END: END
            }
        )
    else:
        workflow.add_edge("mq_agent", END)
    
    # Splunk Agent -> Tools or End
    if splunk_tools:
        workflow.add_conditional_edges(
            "splunk_agent",
            should_continue_splunk,
            {"splunk_tools": "splunk_tools", END: END}
        )
    else:
        workflow.add_edge("splunk_agent", END)
    
    # Redis Agent -> Tools or End
    workflow.add_conditional_edges(
        "redis_agent",
        should_continue_redis,
        {"redis_tools": "redis_tools", END: END}
    )
    
    # Tool Nodes -> Back to Agent (dynamic routing)
    if mq_tools:
        workflow.add_conditional_edges(
            "mq_tools",
            route_tool_output,
            {"mq_agent": "mq_agent"}
        )
    
    if splunk_tools:
        workflow.add_conditional_edges(
            "splunk_tools",
            route_tool_output,
            {"mq_agent": "mq_agent", "splunk_agent": "splunk_agent"}
        )
    
    workflow.add_conditional_edges(
        "redis_tools",
        route_tool_output,
        {"redis_agent": "redis_agent"}
    )
    
    # Placeholder agents go directly to END
    workflow.add_edge("ace_agent", END)
    workflow.add_edge("apigee_agent", END)
    workflow.add_edge("general_agent", END)
    
    return workflow.compile()


# ============================================
# MAIN ENTRY POINT
# ============================================

async def run_query(user_input: str, platform: str = None) -> str:
    """
    Run a query through the orchestrator.
    
    Args:
        user_input: The user's query
        platform: Optional platform hint (mq, splunk, redis, ace, apigee, general)
    
    Returns:
        The agent's response as a string
    """
    model = get_llm()
    manager = MultiMCPSessionManager()
    
    try:
        async with manager.connect() as tools_map:
            # Build Graph
            app = await create_graph(tools_map, model)
            
            # Prepare input
            inputs = {
                "messages": [HumanMessage(content=user_input)],
                "platform": "",
                "sender": ""
            }
            
            # Add platform hint if provided
            if platform and platform.lower() != "general":
                # Normalize platform name: "IBM MQ" -> "mq", "IBM ACE" -> "ace"
                p_normalized = platform.lower().replace("ibm ", "").strip()
                inputs["platform"] = p_normalized
            
            # Run the graph
            final_state = None
            async for output in app.astream(inputs, stream_mode="values"):
                final_state = output
            
            # Extract response
            if final_state and "messages" in final_state:
                last_msg = final_state["messages"][-1]
                if isinstance(last_msg, (AIMessage, HumanMessage)):
                    return last_msg.content
            
            return "I couldn't process that request. Please try again."
            
    except Exception as e:
        import traceback
        error_detail = str(e)
        
        # Handle ExceptionGroup (common with Anyio/MCP)
        if hasattr(e, "exceptions"):
            sub_errors = [str(se) for se in e.exceptions]
            error_detail = f"{error_detail} | Sub-errors: {'; '.join(sub_errors)}"
            
        print("--- [ERROR] FULL TRACEBACK ---")
        traceback.print_exc()
        print("-------------------------------")
        return f"Error processing query: {error_detail}"


async def cleanup_backend():
    """No-op as we handle connections per query now."""
    pass


# ============================================
# GRAPH VISUALIZATION
# ============================================

def generate_graph_png(output_path: str = None) -> str:
    """
    Generate PNG visualization of the agent graph.
    
    Args:
        output_path: Optional path for the output file
    
    Returns:
        Path to the generated PNG file
    """
    import asyncio
    
    if output_path is None:
        output_path = str(parent_dir / "orchestrator_graph.png")
    
    async def _generate():
        # Create a mock model class for visualization (doesn't need API keys)
        class MockModel:
            def bind_tools(self, tools):
                return self
            async def ainvoke(self, messages):
                return AIMessage(content="mock response")
        
        model = MockModel()
        
        # Create mock tools for visualization
        mock_mq_tools = [
            StructuredTool.from_function(
                func=lambda: "mock",
                name="dspmq",
                description="List queue managers"
            ),
            StructuredTool.from_function(
                func=lambda: "mock",
                name="runmqsc",
                description="Run MQSC commands"
            )
        ]
        mock_splunk_tools = [
            StructuredTool.from_function(
                func=lambda: "mock",
                name="search_splunk",
                description="Search Splunk logs"
            ),
            StructuredTool.from_function(
                func=lambda: "mock",
                name="list_indexes",
                description="List Splunk indexes"
            )
        ]
        
        tools_map = {"mq": mock_mq_tools, "splunk": mock_splunk_tools}
        
        app = await create_graph(tools_map, model)
        
        try:
            png_data = app.get_graph().draw_mermaid_png()
            with open(output_path, "wb") as f:
                f.write(png_data)
            print(f"[SUCCESS] Graph saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"[ERROR] Failed to generate graph: {e}")
            print("[INFO] Make sure you have graphviz installed: brew install graphviz")
            return None
    
    return asyncio.run(_generate())


# ============================================
# CLI FOR TESTING
# ============================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("\n" + "="*60)
        print("Platform Support Bot - Backend Test")
        print("="*60)
        
        # Generate graph visualization
        print("\n[INFO] Generating graph visualization...")
        generate_graph_png()
        
        # Test queries
        test_queries = [
            ("What MQ errors occurred today?", "mq"),
            ("Search Splunk logs for errors", "splunk"),
            ("Check Redis cache status", "redis"),
            ("Hello, what can you help with?", None),
        ]
        
        for query, platform in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"Platform hint: {platform or 'auto-detect'}")
            print("-"*60)
            
            response = await run_query(query, platform)
            print(f"Response: {response[:500]}...")
    
    asyncio.run(test())
