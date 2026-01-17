# Platform Support Bot

A specialized agent for diagnosing platform issues using **LangChain**, **FastMCP**, and LLMs.

## Overview
The **Platform Support Bot** is an intelligent orchestrator that routes user queries to specialized agents for different platforms. It uses a modular architecture with LangGraph to manage state and workflow.

### Supported Platforms
- **IBM MQ**: Diagnostics via `dspmq`, `runmqsc` and Splunk logs.
- **Splunk**: Log analysis and search.
- **Redis**: Cache status and log inspection.
- **ACE** (IBM App Connect Enterprise): Integration server checks.
- **Apigee**: API Gateway monitoring.

## Project Structure
The codebase follows a modular design under the `src/` directory:

```
platform_rca_agent/
├── src/
│   ├── modules/
│   │   ├── connections.py   # MCP Connection Manager
│   │   ├── router.py        # Intelligent Query Router
│   │   ├── graph.py         # LangGraph Construction
│   │   └── state.py         # Agent State Definition
│   └── platforms/           # Domain Agents
│       ├── mq.py
│       ├── splunk.py
│       ├── redis.py
│       ├── ace.py
│       ├── apigee.py
│       └── general.py
├── mcpservers/             # Local MCP Server Implementations
├── main_orchestrator.py    # Application Entry Point
├── pyproject.toml          # Project Configuration
└── uv.lock                 # Dependency Lockfile
```

## Setup & Installation

### Prerequisites
- **Python 3.11+**
- **uv** (Package Manager)
  - Install via PowerShell: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Or via pip: `pip install uv`

### Installation
1.  **Clone the repository** and navigate to the root directory.
2.  **Initialize Virtual Environment**:
    ```powershell
    uv venv
    ```
3.  **Install Dependencies**:
    ```powershell
    uv sync
    ```
    *(This installs all dependencies from `uv.lock` / `pyproject.toml`)*

## Configuration

Create a `.env` file in the root directory with the following variables:

```ini
# LLM Provider (gemini or openai)
LLM_CONNECTION=gemini
GOOGLE_API_KEY=your_google_api_key_here
# OR
# LLM_CONNECTION=openai
# OPENAI_API_KEY=your_openai_api_key_here

# Splunk Configuration (Required for Splunk agent)
SPLUNK_HOST=localhost
SPLUNK_PORT=8089
SPLUNK_USERNAME=admin
SPLUNK_PASSWORD=changeme
SPLUNK_SCHEME=https
```

## Running the Application

Start the bot using the `uv` run command or the virtual environment python directly:

```powershell
# Option 1: UV Run
uv run main_orchestrator.py

# Option 2: Active Venv
.venv\Scripts\activate
python main_orchestrator.py
```

## Usage
Once running, you can ask questions like:
- "List all queue managers"
- "Show me MQ errors in the last hour"
- "Check Redis cache status"
- "Help" (to see what I can do)
