import os
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Import from Modular Architecture
from src.connections import MultiMCPSessionManager
from src.graph import create_graph

# Try importing AsyncOpenAI
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

load_dotenv()

async def main():
    print("=" * 60)
    print("Platform Support Bot")
    print("=" * 60)

    # Initialize Model based on LLM_CONNECTION
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
        from langchain_google_genai import ChatGoogleGenerativeAI
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
        # Pass model into graph creator so modules can use it
        app = await create_graph(tools_map, model)
        
        # Optional: Visualize
        try:
             png = app.get_graph().draw_mermaid_png()
             with open("orchestrator_graph.png", "wb") as f:
                 f.write(png)
             print("[INFO] Graph saved to orchestrator_graph.png")
        except Exception as e:
            print(f"[WARN] Graph visualization failed: {e}")

        # Platform Selection API
        SUPPORTED_PLATFORMS = {
            "1": "General",
            "2": "MQ",
            "3": "Splunk",
            "4": "Redis",
            "5": "ACE",
            "6": "Apigee"
        }

        print("\nSelect Platform:")
        for k, v in SUPPORTED_PLATFORMS.items():
            print(f"  {k}. {v}")
        
        choice = await asyncio.to_thread(input, "\nEnter choice (1-6) [Default 1]: ")
        selected_platform = SUPPORTED_PLATFORMS.get(choice.strip(), "General")
        platform_hint = selected_platform.lower()

        print(f"\n[INFO] Starting session for platform: {selected_platform}")
        print("Ready! (Type 'quit' to exit, 'switch' to change platform)")
        print("-" * 60)

        while True:
            try:
                user_input = await asyncio.to_thread(input, f"[{selected_platform}] User: ")
                user_input = user_input.strip()
                
                if user_input.lower() in ["quit", "exit"]:
                    break
                
                if user_input.lower() == "switch":
                    print("\nSelect Platform:")
                    for k, v in SUPPORTED_PLATFORMS.items():
                        print(f"  {k}. {v}")
                    choice = await asyncio.to_thread(input, "\nEnter choice (1-6): ")
                    selected_platform = SUPPORTED_PLATFORMS.get(choice.strip(), "General")
                    platform_hint = selected_platform.lower()
                    print(f"\n[INFO] Switched to platform: {selected_platform}")
                    continue

                if not user_input:
                    continue
                
                print("Processing...")
                
                # Run Graph
                inputs = {
                    "messages": [HumanMessage(content=user_input)],
                    "platform": platform_hint
                }
                
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
