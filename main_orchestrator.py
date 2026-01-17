from typing import List, TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_core.tools import tool, StructuredTool
import os
import asyncio
import sys
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
from sys_prompt import get_system_prompt
import google.generativeai as genai
from pydantic import create_model, Field
from typing import Any, List, Dict, Optional

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

load_dotenv()

# --- Connection Manager ---

class MultiMCPSessionManager:
    """Manages connections to multiple MCP servers"""
    def __init__(self):
        self.sessions = {}
        self.tools = {}
        self.exit_stack = None

    @asynccontextmanager
    async def connect(self):
        # Define server configurations
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Splunk Server Config
        splunk_mcp_path = os.path.join(current_dir, "mcpservers", "splunk_mcp.py")
        splunk_env = os.environ.copy()
        splunk_env.update({
             "SPLUNK_HOST": os.getenv("SPLUNK_HOST", "localhost"),
             "SPLUNK_PORT": os.getenv("SPLUNK_PORT", "8089"),
             "SPLUNK_USERNAME": os.getenv("SPLUNK_USERNAME", ""),
             "SPLUNK_PASSWORD": os.getenv("SPLUNK_PASSWORD", ""),
             "SPLUNK_SCHEME": os.getenv("SPLUNK_SCHEME", "https"),
             "VERIFY_SSL": "false",
        })

        splunk_params = StdioServerParameters(
            command="python",
            args=[splunk_mcp_path, "stdio"],
            env=splunk_env,
        )

        # MQ Server Config
        mq_mcp_path = os.path.join(current_dir, "mcpservers", "mqmcpserver.py")
        mq_params = StdioServerParameters(
            command="python",
            args=[mq_mcp_path],
            env=os.environ.copy(),
        )

        try:
             async with stdio_client(splunk_params) as (splunk_r, splunk_w), \
                        stdio_client(mq_params) as (mq_r, mq_w):
                
                async with ClientSession(splunk_r, splunk_w) as splunk_session, \
                           ClientSession(mq_r, mq_w) as mq_session:
                    
                    self.sessions["splunk"] = splunk_session
                    self.sessions["mq"] = mq_session
                    
                    print("[INFO] Initializing sessions...")
                    await splunk_session.initialize()
                    await mq_session.initialize()
                    
                    print("[INFO] Fetching tools...")
                    # Fetch and convert tools
                    self.tools["splunk"] = await self._fetch_and_convert_tools(splunk_session, "splunk")
                    self.tools["mq"] = await self._fetch_and_convert_tools(mq_session, "mq")
                    
                    yield self.tools

        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            raise

    async def _fetch_and_convert_tools(self, session, source_prefix):
        mcp_tools = await session.list_tools()
        langchain_tools = []
        for tool in mcp_tools.tools:
            langchain_tools.append(self._create_langchain_tool(tool, session, source_prefix))
        return langchain_tools

    def _create_langchain_tool(self, mcp_tool, session, source_prefix):
        tool_name = mcp_tool.name
        tool_description = mcp_tool.description or f"{source_prefix} tool: {tool_name}"

        # 1. Parse JSON Schema to create Pydantic model
        properties = mcp_tool.inputSchema.get("properties", {})
        required_fields = mcp_tool.inputSchema.get("required", [])
        
        fields = {}
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "string") # Default to string
            prop_desc = prop_def.get("description", "")
            
            # Type Mapping
            python_type = str
            if prop_type == "integer": python_type = int
            elif prop_type == "number": python_type = float
            elif prop_type == "boolean": python_type = bool
            elif prop_type == "array": python_type = List[Any]
            elif prop_type == "object": python_type = Dict[str, Any]
            
            # Determine validation (Required vs Optional)
            if prop_name in required_fields:
                # Required: No default value (Use ... usually, or just (type, Field(...)))
                fields[prop_name] = (python_type, Field(description=prop_desc))
            else:
                # Optional: Default is None
                fields[prop_name] = (Optional[python_type], Field(default=None, description=prop_desc))
        
        # Create the model dynamically
        if fields:
            ArgsModel = create_model(f"{tool_name}Args", **fields)
        else:
            ArgsModel = None # No arguments

        async def call_mcp_tool(**kwargs) -> str:
            # print(f"[Calling {source_prefix} tool: {tool_name}]") # Optional: keep or remove. Keeping clean output.
            result = await session.call_tool(tool_name, kwargs)
            if hasattr(result, 'content'):
                 return str(result.content)
            return str(result)

        return StructuredTool.from_function(
            coroutine=call_mcp_tool,
            name=tool_name,
            description=tool_description,
            args_schema=ArgsModel # Pass the schema!
        )


# --- Graph Definitions ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    platform: str # Add platform to state tracking
    sender: str # Track which agent is currently active

# --- Agents & Router Logic ---

class RouterOutput(TypedDict):
    platform: str

# Router Agent
async def platform_router(state: AgentState):
    """
    Analyzes the query to route to the correct platform agent.
    Valid platforms: MQ, Splunk, Redis, ACE, Apigee.
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
    # For robust classification, we can use structured output or just parse the string.
    # Here we'll just ask for the name.
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



# Domain Agents
async def mq_agent(state: AgentState):
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

async def splunk_agent(state: AgentState):
    messages = state["messages"]
    system_instruction = "You are a Splunk expert. Use the provided tools to search logs and inspect indexes."
    model_with_tools = model.bind_tools(splunk_tools_list)
    msgs = [SystemMessage(content=system_instruction)] + list(messages)
    response = await model_with_tools.ainvoke(msgs)
    return {"messages": [response], "sender": "splunk_agent"} # Track sender

# Redis Agent (Mock implementation from main.py pattern)
@tool
def redis_search(query: str) -> str:
    """Search the latest logs in Redis. Use this when user asks for 'latest logs' or 'recent logs' in Redis."""
    return f"[Redis] Implementation pending. Mock result for query: {query}"

async def redis_agent(state: AgentState):
    messages = state["messages"]
    system_instruction = "You are a Redis expert. Use the provided tools to check cache status."
    model_with_tools = model.bind_tools([redis_search]) # Bind mock tool
    msgs = [SystemMessage(content=system_instruction)] + list(messages)
    response = await model_with_tools.ainvoke(msgs)
    return {"messages": [response], "sender": "redis_agent"} # Track sender

# ACE Agent (Placeholder)
async def ace_agent(state: AgentState):
    return {"messages": [AIMessage(content="[ACE Agent] IBM ACE integration is coming soon. I cannot check flows currently.")]}

# Apigee Agent (Placeholder)
async def apigee_agent(state: AgentState):
    return {"messages": [AIMessage(content="[Apigee Agent] Apigee integration is coming soon. I cannot check proxies currently.")]}

# General Agent (Handle out-of-scope)
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


# Edge Logic
def route_from_router(state: dict) -> str:
    return state.get("platform", "splunk_agent") + "_agent"

def route_mq_tools(state: AgentState) -> str:
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

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

def route_tool_output(state: AgentState) -> str:
    """
    Routes tool output back to the agent that called it.
    Uses 'sender' field in state.
    """
    return state.get("sender", "splunk_agent")

# --- Graph Construction ---

async def create_graph(tools_map):
    global mq_tools_list, splunk_tools_list
    mq_tools_list = tools_map["mq"]
    splunk_tools_list = tools_map["splunk"]

    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("platform_router", platform_router)
    workflow.add_node("mq_agent", mq_agent)
    workflow.add_node("splunk_agent", splunk_agent)
    workflow.add_node("redis_agent", redis_agent)
    workflow.add_node("ace_agent", ace_agent)
    workflow.add_node("apigee_agent", apigee_agent)
    workflow.add_node("general_agent", general_agent)
    
    # Tool Nodes
    workflow.add_node("mq_tools", ToolNode(mq_tools_list))
    workflow.add_node("splunk_tools", ToolNode(splunk_tools_list)) 
    workflow.add_node("redis_tools", ToolNode([redis_search])) # Redis tools

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
        route_mq_tools, 
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


# --- Main ---

async def main():
    print("=" * 60)
    print("Platform Support Bot")
    print("=" * 60)

    # Initialize Model based on LLM_CONNECTION
    global model
    llm_type = os.getenv("LLM_CONNECTION", "gemini").lower()
    
    if llm_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        if not AsyncOpenAI:
            raise ImportError("openai package not installed. Run 'pip install openai'")
        
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key)
        print("[INFO] Using OpenAI (gpt-4o)")
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
        print("[INFO] Using Gemini (gemini-1.5-flash)")

    # Initialize Connections
    manager = MultiMCPSessionManager()
    
    print("Connecting to MCP servers...")
    async with manager.connect() as tools_map:
        print(f"[OK] Connected. Tools loaded:")
        for source, tools in tools_map.items():
            tool_names = [t.name for t in tools]
            print(f"  - {source}: {', '.join(tool_names)}")
        
        # Build Graph
        app = await create_graph(tools_map)
        
        # Optional: Visualize
        try:
             png = app.get_graph().draw_mermaid_png()
             with open("orchestrator_graph.png", "wb") as f:
                 f.write(png)
             print("[INFO] Graph saved to orchestrator_graph.png")
        except Exception as e:
            print(f"[WARN] Graph visualization failed: {e}")

        print("\nReady! (Type 'quit' to exit)")
        print("-" * 60)

        while True:
            try:
                user_input = await asyncio.to_thread(input, "User: ")
                user_input = user_input.strip()
                if user_input.lower() in ["quit", "exit"]:
                    break
                if not user_input:
                    continue
                
                print("Processing...")
                
                # Run Graph
                inputs = {"messages": [HumanMessage(content=user_input)]}
                
                # Stream results
                async for output in app.astream(inputs, stream_mode="values"):
                    pass
                
                # Get final state
                final_state = output
                last_msg = final_state["messages"][-1]
                
                if isinstance(last_msg, AIMessage):
                    print(f"\nAgent: {last_msg.content}\n")
                elif isinstance(last_msg, BaseMessage):
                     print(f"\nResult: {last_msg.content}\n")

            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
