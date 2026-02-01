"""
MCP Connection Manager - Connects to MQ and Splunk MCP servers and provides tools to the orchestrator.

This module creates connections to the FastMCP servers and converts their tools
into LangChain-compatible tools for use in the agent system.
"""

import os
import asyncio
import subprocess
import sys
from contextlib import asynccontextmanager
from typing import Dict, List, Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPToolWrapper:
    """Wrapper to convert MCP tools to LangChain-compatible tools"""
    
    def __init__(self, session: ClientSession, tool_info: dict):
        self.session = session
        self.tool_info = tool_info
        self.name = tool_info.name
        self.description = tool_info.description or f"MCP Tool: {self.name}"
        
    async def ainvoke(self, args: dict) -> str:
        """Async invoke the MCP tool"""
        try:
            result = await self.session.call_tool(self.name, arguments=args)
            # Extract content from the result
            if hasattr(result, 'content') and result.content:
                if isinstance(result.content, list):
                    return "\n".join(
                        str(item.text) if hasattr(item, 'text') else str(item) 
                        for item in result.content
                    )
                return str(result.content)
            return str(result)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"
    
    def invoke(self, args: dict) -> str:
        """Sync invoke wrapper"""
        return asyncio.run(self.ainvoke(args))


class MCPSessionManager:
    """Manages a connection to a single MCP server"""
    
    def __init__(self, server_script: str, server_name: str):
        self.server_script = server_script
        self.server_name = server_name
        self.session = None
        self.tools = []
        self._read_stream = None
        self._write_stream = None
        
    async def connect(self):
        """Connect to the MCP server and retrieve tools"""
        print(f"[MCP] Connecting to {self.server_name}...")
        
        # Create server parameters for stdio transport
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
            cwd=os.path.dirname(self.server_script) or "."
        )
        
        # This will be called within the context manager
        return server_params
    
    async def get_tools(self, session: ClientSession) -> List[MCPToolWrapper]:
        """Get all tools from the connected MCP session"""
        self.session = session
        
        # List available tools from the server
        tools_response = await session.list_tools()
        
        self.tools = []
        for tool_info in tools_response.tools:
            wrapped_tool = MCPToolWrapper(session, tool_info)
            self.tools.append(wrapped_tool)
            print(f"[MCP] Loaded tool: {tool_info.name}")
        
        return self.tools


class MultiMCPSessionManager:
    """Manages connections to multiple MCP servers (MQ and Splunk)"""
    
    def __init__(self):
        # Get the directory where this script is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        mcpservers_dir = os.path.join(base_dir, "mcpservers")
        
        self.server_configs = {
            "mq": {
                "script": os.path.join(mcpservers_dir, "mqmcpserver.py"),
                "name": "IBM MQ MCP Server"
            },
            "splunk": {
                "script": os.path.join(mcpservers_dir, "splunk_mcp.py"),
                "name": "Splunk MCP Server",
                "args": ["stdio"]  # Run in stdio mode, not SSE
            }
        }
        
        self._sessions = {}
        self._contexts = {}
    
    @asynccontextmanager
    async def connect(self):
        """
        Connect to all MCP servers and yield a dictionary of tools.
        
        Usage:
            async with MultiMCPSessionManager().connect() as mcp_tools:
                mq_tools = mcp_tools["mq"]
                splunk_tools = mcp_tools["splunk"]
        """
        mcp_tools = {"mq": [], "splunk": []}
        active_contexts = []
        
        try:
            for server_key, config in self.server_configs.items():
                script_path = config["script"]
                server_name = config["name"]
                
                if not os.path.exists(script_path):
                    print(f"[WARN] {server_name} script not found at: {script_path}")
                    continue
                
                print(f"[MCP] Starting {server_name}...")
                
                try:
                    # Get extra args from config (e.g., "stdio" for splunk)
                    extra_args = config.get("args", [])
                    
                    # Create server parameters
                    server_params = StdioServerParameters(
                        command=sys.executable,
                        args=[script_path] + extra_args,
                        cwd=os.path.dirname(script_path) or "."
                    )
                    
                    # Enter the stdio_client context
                    client_context = stdio_client(server_params)
                    read_stream, write_stream = await client_context.__aenter__()
                    active_contexts.append(client_context)
                    
                    # Create and initialize the session
                    session = ClientSession(read_stream, write_stream)
                    session_context = session
                    await session.__aenter__()
                    active_contexts.append(session)
                    
                    # Initialize the session
                    await session.initialize()
                    
                    # Get tools from the server
                    tools_response = await session.list_tools()
                    
                    for tool_info in tools_response.tools:
                        wrapped_tool = MCPToolWrapper(session, tool_info)
                        mcp_tools[server_key].append(wrapped_tool)
                        print(f"[MCP] [{server_key.upper()}] Loaded tool: {tool_info.name}")
                    
                    print(f"[MCP] {server_name} connected successfully with {len(mcp_tools[server_key])} tools")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to connect to {server_name}: {e}")
                    import traceback
                    traceback.print_exc()
            
            yield mcp_tools
            
        finally:
            # Clean up all contexts in reverse order
            for context in reversed(active_contexts):
                try:
                    await context.__aexit__(None, None, None)
                except Exception as e:
                    print(f"[WARN] Error closing context: {e}")


# Example usage and testing
if __name__ == "__main__":
    async def test_connection():
        """Test the MCP connection"""
        manager = MultiMCPSessionManager()
        
        async with manager.connect() as tools:
            print("\n" + "="*60)
            print("MCP Connection Test Results")
            print("="*60)
            
            for server_key, tool_list in tools.items():
                print(f"\n{server_key.upper()} Tools ({len(tool_list)}):")
                for tool in tool_list:
                    print(f"  - {tool.name}: {tool.description[:50]}...")
            
            print("\n" + "="*60)
            print("Connection test complete!")
            print("="*60)
    
    asyncio.run(test_connection())
