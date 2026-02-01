import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager, AsyncExitStack
from typing import TypedDict, Any, List, Dict, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field

class MultiMCPSessionManager:
    """Manages connections to multiple MCP servers with fault tolerance"""
    def __init__(self):
        self.sessions = {}
        self.tools = {}

    @asynccontextmanager
    async def connect(self):
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

        async with AsyncExitStack() as stack:
            # Try connecting to Splunk
            try:
                splunk_transport = await stack.enter_async_context(stdio_client(splunk_params))
                splunk_session = await stack.enter_async_context(ClientSession(splunk_transport[0], splunk_transport[1]))
                await splunk_session.initialize()
                self.sessions["splunk"] = splunk_session
                self.tools["splunk"] = await self._fetch_and_convert_tools(splunk_session, "splunk")
                print("[INFO] Connected to Splunk MCP server.")
            except Exception as e:
                print(f"[WARN] Splunk connection failed: {e}")
                self.tools["splunk"] = []

            # Try connecting to MQ
            try:
                mq_transport = await stack.enter_async_context(stdio_client(mq_params))
                mq_session = await stack.enter_async_context(ClientSession(mq_transport[0], mq_transport[1]))
                await mq_session.initialize()
                self.sessions["mq"] = mq_session
                self.tools["mq"] = await self._fetch_and_convert_tools(mq_session, "mq")
                print("[INFO] Connected to MQ MCP server.")
            except Exception as e:
                print(f"[WARN] MQ connection failed: {e}. Falling back to Splunk-only mode for MQ queries.")
                self.tools["mq"] = []

            yield self.tools

    async def _fetch_and_convert_tools(self, session, source_prefix):
        mcp_tools = await session.list_tools()
        langchain_tools = []
        for tool in mcp_tools.tools:
            langchain_tools.append(self._create_langchain_tool(tool, session, source_prefix))
        return langchain_tools

    def _create_langchain_tool(self, mcp_tool, session, source_prefix):
        tool_name = mcp_tool.name
        tool_description = mcp_tool.description or f"{source_prefix} tool: {tool_name}"

        properties = mcp_tool.inputSchema.get("properties", {})
        required_fields = mcp_tool.inputSchema.get("required", [])
        
        fields = {}
        for prop_name, prop_def in properties.items():
            prop_type = prop_def.get("type", "string")
            prop_desc = prop_def.get("description", "")
            
            python_type = str
            if prop_type == "integer": python_type = int
            elif prop_type == "number": python_type = float
            elif prop_type == "boolean": python_type = bool
            elif prop_type == "array": python_type = List[Any]
            elif prop_type == "object": python_type = Dict[str, Any]
            
            if prop_name in required_fields:
                fields[prop_name] = (python_type, Field(description=prop_desc))
            else:
                fields[prop_name] = (Optional[python_type], Field(default=None, description=prop_desc))
        
        if fields:
            ArgsModel = create_model(f"{tool_name}Args", **fields)
        else:
            ArgsModel = None

        async def call_mcp_tool(**kwargs) -> str:
            try:
                result = await session.call_tool(tool_name, kwargs)
                if hasattr(result, 'content'):
                     return str(result.content)
                return str(result)
            except Exception as e:
                return f"Error executing tool {tool_name}: {str(e)}"

        return StructuredTool.from_function(
            coroutine=call_mcp_tool,
            name=tool_name,
            description=tool_description,
            args_schema=ArgsModel
        )
