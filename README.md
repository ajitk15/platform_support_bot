# Platform Support Bot

This guide details how to set up and run the Platform RCA Agent using `uv` and `python` on Windows.

## Prerequisites

- **Python 3.11+**
- **uv**: A fast Python package installer and resolver.
  - Install via PowerShell: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Or via pip: `pip install uv`

## Installation Steps

1.  **Navigate to the repository**
    Open your terminal in the project root.

2.  **Initialize Virtual Environment**
    Create a new virtual environment using `uv`:
    ```powershell
    uv venv
    ```

3.  **Activate Virtual Environment**
    ```powershell
    .venv\Scripts\activate
    ```

4.  **Install Dependencies**
    Sync dependencies from `uv.lock`:
    ```powershell
    uv sync
    ```
    *Note: This command installs all dependencies defined in `pyproject.toml` and locked in `uv.lock`.*

## Configuration

1.  **Environment Variables**
    Ensure a `.env` file exists in the root directory. It should contain the following keys:
    - `GOOGLE_API_KEY` (for Gemini) or `OPENAI_API_KEY` (for OpenAI)
    - `LLM_CONNECTION` (set to `gemini` or `openai`, defaults to `gemini`)
    - Splunk Configuration: `SPLUNK_HOST`, `SPLUNK_PORT`, `SPLUNK_USERNAME`, `SPLUNK_PASSWORD`
    
    *Note: A `.env` file is present in the workspace. Verify its contents.*

## Running the Application

To start the agent orchestrator:

```powershell
# Option 1: Using the activated virtual environment
python main_orchestrator.py

# Option 2: Using uv run (handles venv automatically)
uv run main_orchestrator.py
```

### Troubleshooting
- **Entry Point Mismatch**: The `pyproject.toml` lists `platform-rca-agent = "main:main"`, but the main file is `main_orchestrator.py`. Do not try to run `platform-rca-agent` directly unless you rename the file. Use the commands above.
- **MCP Servers**: The application expects `mcpservers/splunk_mcp.py` and `mcpservers/mqmcpserver.py` to be present.
