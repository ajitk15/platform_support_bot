import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
from typing import TypedDict, Any, List, Dict, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field

class MultiMCPSessionManager:
    """Manages connections to multiple MCP servers"""
    def __init__(self):
        self.sessions = {}
        self.tools = {}
        self.exit_stack = None

    @asynccontextmanager
    async def connect(self):
        # Define server configurations
        # NOTE: Assuming main_orchestrator.py is in root, and mcpservers is in root. 
        # But this file is in src/. Adjusted path logic needed.
        # Current dir is src/. Parent is root.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        
        # Splunk Server Config
        splunk_mcp_path = os.path.join(root_dir, "mcpservers", "splunk_mcp.py")
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
        mq_mcp_path = os.path.join(root_dir, "mcpservers", "mqmcpserver.py")
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
