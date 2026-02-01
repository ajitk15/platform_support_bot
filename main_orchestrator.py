import os
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import operator
from dotenv import load_dotenv

# Import the system prompt configuration
from sys_prompt import get_system_prompt, SPLUNK_CONFIG

load_dotenv()

# ============================================
# STATE DEFINITION
# ============================================
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    current_agent: str
    tools_called: Annotated[list, operator.add]
    final_response: str
    error: str

# ============================================
# LLM INITIALIZATION WITH FALLBACK
# ============================================
def get_llm():
    """Get LLM with Gemini primary, OpenAI fallback"""
    try:
        # Primary: Gemini Flash 2.0
        gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.2,
        )
        print("[INFO] Using Gemini 2.0 Flash")
        return gemini_llm
    except Exception as e:
        print(f"[WARN] Gemini failed: {e}. Falling back to OpenAI GPT-4")
        openai_llm = ChatOpenAI(
            model="gpt-4",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.2,
        )
        return openai_llm

# ============================================
# ROUTING LOGIC
# ============================================
def platform_router(state: AgentState) -> AgentState:
    """Route user query to appropriate agent based on keywords"""
    last_message = state["messages"][-1].content.lower()
    
    # MQ-related keywords
    mq_keywords = ["mq", "queue", "channel", "qmgr", "queue manager", "amq", "ibm mq"]
    # Splunk-related keywords
    splunk_keywords = ["splunk", "logs", "search", "spl", "index", "error", "warning"]
    # Apigee keywords
    apigee_keywords = ["apigee", "api", "proxy", "api gateway"]
    # ACE keywords
    ace_keywords = ["ace", "app connect", "integration", "esb", "message flow"]
    # Redis keywords
    redis_keywords = ["redis", "cache", "key-value"]
    
    # Determine the target agent
    target_agent = "general_agent"
    
    if any(keyword in last_message for keyword in mq_keywords):
        target_agent = "mq_agent"
    elif any(keyword in last_message for keyword in splunk_keywords):
        target_agent = "splunk_agent"
    elif any(keyword in last_message for keyword in apigee_keywords):
        target_agent = "apigee_agent"
    elif any(keyword in last_message for keyword in ace_keywords):
        target_agent = "ace_agent"
    elif any(keyword in last_message for keyword in redis_keywords):
        target_agent = "redis_agent"
    
    print(f"[ROUTER] Routing to {target_agent}")
    
    # Return updated state with the target agent set
    return {"current_agent": target_agent}

# ============================================
# AGENT NODES
# ============================================

async def mq_agent(state: AgentState, mq_tools: list) -> AgentState:
    """MQ Agent - handles MQ-specific queries with MQ tools"""
    print("[MQ_AGENT] Processing query...")
    
    llm = get_llm()
    system_prompt = get_system_prompt(mq_tools)
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(mq_tools)
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        # Get LLM response with potential tool calls
        response = llm_with_tools.invoke(messages)
        state["messages"].append(response)
        
        # Execute tools if LLM requested them
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"[MQ_AGENT] Executing tools: {[tc['name'] for tc in response.tool_calls]}")
            
            for tool_call in response.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                
                # Find and execute the tool
                tool_to_execute = next((t for t in mq_tools if t.name == tool_name), None)
                
                if tool_to_execute:
                    print(f"[MQ_AGENT] Calling {tool_name} with args: {tool_args}")
                    tool_result = await tool_to_execute.ainvoke(tool_args)
                    print(f"[MQ_AGENT] Tool result: {tool_result[:200]}...")  # Show first 200 chars
                    
                    # Add tool result to messages
                    from langchain_core.messages import ToolMessage
                    state["messages"].append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call['id']
                        )
                    )
                    state["tools_called"].append(tool_name)
                else:
                    print(f"[WARNING] Tool {tool_name} not found!")
            
            # Get final response after tool execution
            final_response = llm.invoke(state["messages"])
            state["messages"].append(final_response)
            state["final_response"] = final_response.content
        else:
            # No tools called, use direct response
            state["final_response"] = response.content
        
        state["current_agent"] = "mq_agent"
        
    except Exception as e:
        print(f"[ERROR] MQ Agent failed: {e}")
        import traceback
        traceback.print_exc()
        state["error"] = str(e)
        state["final_response"] = f"MQ Agent encountered an error: {e}"
    
    return state

async def splunk_agent(state: AgentState, splunk_tools: list) -> AgentState:
    """Splunk Agent - handles Splunk-specific queries"""
    print("[SPLUNK_AGENT] Processing query...")
    
    llm = get_llm()
    system_prompt = get_system_prompt(splunk_tools)
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(splunk_tools)
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        # Get LLM response with potential tool calls
        response = llm_with_tools.invoke(messages)
        state["messages"].append(response)
        
        # Execute tools if LLM requested them
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"[SPLUNK_AGENT] Executing tools: {[tc['name'] for tc in response.tool_calls]}")
            
            for tool_call in response.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                
                # Find and execute the tool
                tool_to_execute = next((t for t in splunk_tools if t.name == tool_name), None)
                
                if tool_to_execute:
                    print(f"[SPLUNK_AGENT] Calling {tool_name} with args: {tool_args}")
                    tool_result = await tool_to_execute.ainvoke(tool_args)
                    print(f"[SPLUNK_AGENT] Tool result: {tool_result[:200]}...")  # Show first 200 chars
                    
                    # Add tool result to messages
                    from langchain_core.messages import ToolMessage
                    state["messages"].append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call['id']
                        )
                    )
                    state["tools_called"].append(tool_name)
                else:
                    print(f"[WARNING] Tool {tool_name} not found!")
            
            # Get final response after tool execution
            final_response = llm.invoke(state["messages"])
            state["messages"].append(final_response)
            state["final_response"] = final_response.content
        else:
            # No tools called, use direct response
            state["final_response"] = response.content
        
        state["current_agent"] = "splunk_agent"
        
    except Exception as e:
        print(f"[ERROR] Splunk Agent failed: {e}")
        import traceback
        traceback.print_exc()
        state["error"] = str(e)
        state["final_response"] = f"Splunk Agent encountered an error: {e}"
    
    return state

def general_agent(state: AgentState) -> AgentState:
    """General Agent - placeholder for general queries"""
    print("[GENERAL_AGENT] Processing query...")
    
    response_message = AIMessage(
        content="👋 Hi! I'm the General Agent. I'll be working soon to handle general queries and coordination. "
                "For now, please try asking about MQ or Splunk operations!"
    )
    
    state["messages"].append(response_message)
    state["current_agent"] = "general_agent"
    state["final_response"] = response_message.content
    
    return state

def apigee_agent(state: AgentState) -> AgentState:
    """Apigee Agent - placeholder"""
    print("[APIGEE_AGENT] Processing query...")
    
    response_message = AIMessage(
        content="👋 Hi! I'm the Apigee Agent. I'll be working soon to help with API management, "
                "proxy configurations, and API analytics. Stay tuned!"
    )
    
    state["messages"].append(response_message)
    state["current_agent"] = "apigee_agent"
    state["final_response"] = response_message.content
    
    return state

def ace_agent(state: AgentState) -> AgentState:
    """ACE Agent - placeholder"""
    print("[ACE_AGENT] Processing query...")
    
    response_message = AIMessage(
        content="👋 Hi! I'm the ACE (App Connect Enterprise) Agent. I'll be working soon to assist with "
                "integration flows, message brokers, and ESB operations. Coming soon!"
    )
    
    state["messages"].append(response_message)
    state["current_agent"] = "ace_agent"
    state["final_response"] = response_message.content
    
    return state

def redis_agent(state: AgentState) -> AgentState:
    """Redis Agent - placeholder"""
    print("[REDIS_AGENT] Processing query...")
    
    response_message = AIMessage(
        content="👋 Hi! I'm the Redis Agent. I'll be working soon to help with cache operations, "
                "key-value queries, and Redis performance monitoring. Under development!"
    )
    
    state["messages"].append(response_message)
    state["current_agent"] = "redis_agent"
    state["final_response"] = response_message.content
    
    return state

# ============================================
# GRAPH CONSTRUCTION
# ============================================
def create_agent_graph(mcp_tools: dict):
    """Create the LangGraph workflow with all agents"""
    
    # Extract tools by type
    mq_tools = mcp_tools.get("mq", [])
    splunk_tools = mcp_tools.get("splunk", [])
    
    # Create async wrapper functions for agents that need tools
    async def mq_agent_wrapper(state: AgentState) -> AgentState:
        return await mq_agent(state, mq_tools)
    
    async def splunk_agent_wrapper(state: AgentState) -> AgentState:
        return await splunk_agent(state, splunk_tools)
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("platform_router", platform_router)
    workflow.add_node("mq_agent", mq_agent_wrapper)
    workflow.add_node("splunk_agent", splunk_agent_wrapper)
    workflow.add_node("general_agent", general_agent)
    workflow.add_node("apigee_agent", apigee_agent)
    workflow.add_node("ace_agent", ace_agent)
    workflow.add_node("redis_agent", redis_agent)
    
    # Set entry point
    workflow.set_entry_point("platform_router")
    
    # Add conditional edges from router
    workflow.add_conditional_edges(
        "platform_router",
        lambda state: state["current_agent"],
        {
            "mq_agent": "mq_agent",
            "splunk_agent": "splunk_agent",
            "general_agent": "general_agent",
            "apigee_agent": "apigee_agent",
            "ace_agent": "ace_agent",
            "redis_agent": "redis_agent",
        }
    )
    
    # All agents go to END
    workflow.add_edge("mq_agent", END)
    workflow.add_edge("splunk_agent", END)
    workflow.add_edge("general_agent", END)
    workflow.add_edge("apigee_agent", END)
    workflow.add_edge("ace_agent", END)
    workflow.add_edge("redis_agent", END)
    
    return workflow.compile()

# ============================================
# MAIN ORCHESTRATOR
# ============================================
async def run_agent_system(user_query: str, mcp_tools: dict):
    """Main entry point for the agent system"""
    
    print(f"\n{'='*60}")
    print(f"[USER QUERY] {user_query}")
    print(f"{'='*60}\n")
    
    # Create the graph
    agent_graph = create_agent_graph(mcp_tools)
    
    # Initialize state
    initial_state = {
        "messages": [HumanMessage(content=user_query)],
        "current_agent": "",
        "tools_called": [],
        "final_response": "",
        "error": ""
    }
    
    # Run the graph
    try:
        final_state = await agent_graph.ainvoke(initial_state)
        
        print(f"\n{'='*60}")
        print(f"[FINAL RESPONSE]")
        print(f"{'='*60}")
        print(f"Agent: {final_state['current_agent']}")
        print(f"Tools Called: {final_state['tools_called']}")
        print(f"Response: {final_state['final_response']}")
        
        if final_state.get('error'):
            print(f"Error: {final_state['error']}")
        
        return final_state
        
    except Exception as e:
        print(f"[ERROR] Agent system failed: {e}")
        return {"error": str(e), "final_response": "System error occurred"}

# ============================================
# GRAPH VISUALIZATION
# ============================================
def generate_graph_png(output_path: str = "agent_graph.png"):
    """Generate PNG visualization of the agent graph"""
    try:
        from IPython.display import Image, display
        
        # Create a mock tools dict for visualization
        mock_tools = {"mq": [], "splunk": []}
        
        # Create the graph
        agent_graph = create_agent_graph(mock_tools)
        
        # Generate PNG
        png_data = agent_graph.get_graph().draw_mermaid_png()
        
        # Save to file
        with open(output_path, "wb") as f:
            f.write(png_data)
        
        print(f"[SUCCESS] Graph visualization saved to: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"[ERROR] Failed to generate graph PNG: {e}")
        print("[INFO] Make sure you have these installed:")
        print("  pip install grandalf pygraphviz")
        return None

# ============================================
# USAGE EXAMPLE
# ============================================
if __name__ == "__main__":
    import asyncio
    from mcp_connection import MultiMCPSessionManager
    
    async def main():
        # Generate graph visualization first
        print("\n[INFO] Generating graph visualization...")
        generate_graph_png("agent_graph.png")
        
        # Initialize MCP connections
        session_manager = MultiMCPSessionManager()
        
        async with session_manager.connect() as mcp_tools:
            print("[INFO] MCP tools loaded successful ly!")
            print(f"[INFO] MQ Tools: {[t.name for t in mcp_tools['mq']]}")
            print(f"[INFO] Splunk Tools: {[t.name for t in mcp_tools['splunk']]}")
            
            # Example queries
            queries = [
                "Are there any MQ errors in the last 24 hours?",
                "Show me Splunk logs for queue manager QM1",
                "What's the status of my Apigee proxies?",
                "Help me with ACE integration flows",
            ]
            
            for query in queries:
                await run_agent_system(query, mcp_tools)
                print("\n")
    
    asyncio.run(main())