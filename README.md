# Platform Support Bot

A specialized agent for diagnosing platform issues using **LangChain**, **FastMCP**, and LLMs.

## Overview
The **Platform Support Bot** is an intelligent orchestrator that routes user queries to specialized agents for different platforms. It uses a modular architecture with LangGraph to manage state and workflow.

### Supported Platforms
- **IBM MQ**: Diagnostics via live probes (`dspmq`, `runmqsc`) and Splunk logs fallback.
- **Splunk**: Log analysis and search across multiple indexes.
- **Redis**: Cache status and log inspection.
- **ACE** (IBM App Connect Enterprise): Integration server checks.
- **Apigee**: API Gateway monitoring.

## Project Structure
```
platform_support_bot/
├── src/
│   ├── connections.py       # MCP Connection Manager (Fault-Tolerant)
│   ├── graph.py             # LangGraph Construction Logic
│   ├── router.py            # Intelligent Query Categorization
│   ├── state.py             # LangGraph State Definitions
│   └── platforms/           # Specialized Platform Agents
│       ├── mq.py            # IBM MQ Agent
│       ├── splunk.py        # Splunk Search Agent
│       ├── redis.py         # Redis Diagnostic Agent
│       ├── ace.py           # IBM ACE Agent
│       └── apigee.py        # Apigee Gateway Agent
├── streamlit_app/           # Modern Web Interface
│   ├── app.py               # Streamlit UI (Home + Chat)
│   ├── backend.py           # Streamlit-to-Graph Bridge
│   └── .streamlit/          # Streamlit Configuration (Theme/Port)
├── mcpservers/             # FastMCP Server Implementations
│   ├── mqmcpserver.py      # IBM MQ MCP Connector
│   └── splunk_mcp.py       # Splunk MCP Connector
├── main_orchestrator.py    # CLI Diagnostic Interface
├── pyproject.toml          # Project Dependencies & UV Config
├── uv.lock                 # Dependency Lockfile
├── .env                    # Environment Credentials (LLM, Splunk, etc.)
└── .gitignore              # Standard Python Git Exclusions
```

## Setup & Installation

### Prerequisites
- **Python 3.11+**
- **uv** (Recommended Package Manager)
  - Install via pip: `pip install uv`

### Installation
1.  **Clone the repository** and navigate to the root directory.
2.  **Install Dependencies**:
    ```powershell
    uv sync
    ```

## Configuration

Create a `.env` file in the root directory with your credentials:

```ini
# LLM Provider (gemini or openai)
LLM_CONNECTION=openai
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_openai_api_key_here
# Splunk Configuration
SPLUNK_HOST=localhost
SPLUNK_PORT=8089
SPLUNK_USERNAME=your_user
SPLUNK_PASSWORD=your_password
SPLUNK_SCHEME=https
VERIFY_SSL=false
SPLUNK_URL=https://localhost:8089
```

## Running the Application

### 🚀 Option 1: Modern Web Interface (Recommended)
Provides a compact, tile-based landing page and professional chat UI.

```powershell
uv run streamlit run streamlit_app/app.py
```
*Access via browser at `http://localhost:8501` (or the port specified in terminal).*

### 💻 Option 2: CLI Interface
For quick terminal-based diagnostics:

```powershell
uv run main_orchestrator.py
```

## Usage
Once running, you can ask platforms-specific questions like:
- "List all queue managers"
- "Show me MQ errors in the last hour"
- "Check Redis cache status"
- "Help"
