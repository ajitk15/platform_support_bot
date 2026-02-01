# Streamlit Frontend for Platform Support Bot

A modern, compact web interface for the Platform Support Bot built with Streamlit.

## Features

- 🎨 **Modern UI**: Glassmorphism effects, gradients, and smooth animations
- 🔄 **Platform Selection**: Easy dropdown to switch between platforms
- 💬 **Chat Interface**: Clean message history with color-coded messages
- ⚡ **Real-time**: Instant responses from the backend orchestrator
- 📱 **Responsive**: Works on desktop and mobile devices

## Supported Platforms

- **General** 💬 - General queries and help
- **MQ** 📬 - IBM MQ (queues, channels, managers)
- **Splunk** 🔍 - Log analysis and search
- **Redis** ⚡ - Cache status and memory
- **ACE** 🔗 - IBM App Connect Enterprise
- **Apigee** 🌐 - API Gateway monitoring

## Running the App

### Prerequisites

Make sure you have completed the setup in the main README:
1. Installed dependencies with `uv sync`
2. Configured `.env` file with API keys

### Start the Streamlit App

```powershell
# From the project root directory
uv run streamlit run streamlit_app/app.py
```

The app will open automatically in your browser at `http://localhost:8501`

## Usage

1. **Select Platform**: Use the sidebar dropdown to choose your platform
2. **Ask Questions**: Type your query in the input box
3. **Get Answers**: The bot will process your request and respond
4. **Clear Chat**: Use the "Clear Chat" button to start fresh

## Example Queries

- "List all queue managers"
- "Show MQ errors in the last hour"
- "Check Redis cache status"
- "Search Splunk logs for errors"
- "Help"

## Architecture

```
streamlit_app/
├── app.py              # Main Streamlit UI
├── backend.py          # Backend integration with orchestrator
└── .streamlit/
    └── config.toml     # Streamlit theme configuration
```

The app integrates with the existing `src/` modules:
- Uses `MultiMCPSessionManager` for MCP connections
- Leverages `create_graph()` for orchestration
- Supports both Gemini and OpenAI models

## Customization

### Theme Colors

Edit `streamlit_app/.streamlit/config.toml` to customize colors:

```toml
[theme]
primaryColor="#667eea"      # Primary accent color
backgroundColor="#0f0c29"    # Main background
secondaryBackgroundColor="#1a1a2e"  # Sidebar background
textColor="#ffffff"          # Text color
```

### Platform Icons

Modify the `PLATFORMS` dictionary in `app.py` to change icons and colors.

## Troubleshooting

**Issue**: "Module not found" errors
- **Solution**: Make sure you're running from the project root directory

**Issue**: Connection errors
- **Solution**: Verify your `.env` file has the correct API keys and Splunk credentials

**Issue**: Slow responses
- **Solution**: Check your internet connection and API rate limits
