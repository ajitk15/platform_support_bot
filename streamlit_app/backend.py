"""
Backend integration module for Streamlit app.
Handles async orchestrator calls and session management.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.connections import MultiMCPSessionManager
from src.graph import create_graph

# Load environment variables
load_dotenv(parent_dir / ".env")

from contextlib import AsyncExitStack

async def run_query(user_input: str, platform: str = None) -> str:
    """
    Run a query through the orchestrator.
    """
    # Initialize Model based on LLM_CONNECTION
    llm_type = os.getenv("LLM_CONNECTION", "gemini").lower()
    
    if llm_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key)
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

    manager = MultiMCPSessionManager()
    
    try:
        # Use a fresh connection for each query to avoid event loop mismatch in Streamlit
        async with manager.connect() as tools_map:
            # Build Graph
            app = await create_graph(tools_map, model)
            
            # Prepare input
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Add platform hint if provided
            if platform and platform != "General":
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
