import streamlit as st
import asyncio
import os
import sys
from pathlib import Path

# Add current and parent directory to path to import from src and local modules
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(parent_dir))

from backend import run_query

# Page configuration
st.set_page_config(
    page_title="Platform Support Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern, compact UI (Light Theme)
st.markdown("""
<style>
    /* Reduce top padding and keep sidebar toggle accessible */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    .stAppDeployButton, #MainMenu {
        visibility: hidden;
    }
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Main container styling */
    .main {
        background: #f8f9fa;
        color: #2c3e50;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e9ecef;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem !important;
    }
    
    /* Platform selector styling */
    .stSelectbox {
        margin-bottom: 1rem;
    }
    
    /* Compact Chat message styling */
    .chat-row {
        display: flex;
        flex-direction: column;
        margin-bottom: 0.75rem;
        animation: fadeIn 0.3s ease-in;
    }
    
    .chat-bubble {
        padding: 0.6rem 0.8rem;
        border-radius: 12px;
        max-width: 85%;
        font-size: 0.95rem;
        line-height: 1.4;
        position: relative;
        border: 1px solid #e9ecef;
    }
    
    .message-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .user-row {
        align-items: flex-end;
    }
    
    .user-bubble {
        background-color: #ffffff;
        border-right: 3px solid #3498db;
        color: #2c3e50;
    }
    
    .bot-row {
        align-items: flex-start;
    }
    
    .bot-bubble {
        background-color: #f8fbff;
        border-left: 3px solid #9b59b6;
        color: #2c3e50;
    }
    
    .platform-badge {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        background: #eef2f7;
        color: #5a6b7d;
        border: 1px solid #d1d9e6;
    }
    
    /* Input box styling */
    .stTextInput > div > div > input {
        background: #ffffff;
        border: 1px solid #ced4da;
        border-radius: 10px;
        color: #2c3e50;
        padding: 0.75rem;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(52, 152, 219, 0.3);
    }
    
    /* Header styling */
    h1, h2, h3 {
        color: #2c3e50;
        font-weight: 700;
    }
    
    /* Loading animation */
    .thinking {
        display: inline-block;
        color: #7f8c8d;
        animation: pulse 1.5s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.6; }
        50% { opacity: 1; }
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #ccc;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #999;
    }
    
    /* Info box styling */
    .info-container {
        padding: 1rem;
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        margin-top: 1rem;
    }
    
    /* Tile Grid Styling - Compact & Clickable */
    .tile-grid [data-testid="column"] button {
        height: 70px !important;
        background: #ffffff !important;
        border: 1px solid #e9ecef !important;
        border-radius: 12px !important;
        color: #2c3e50 !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        margin-bottom: 30px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    }
    
    .tile-grid [data-testid="column"] button:hover {
        border-color: #3498db !important;
        transform: translateY(-3px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
        background-color: #f8f9fa !important;
    }

    .landing-title { text-align: center; margin-top: 5rem; margin-bottom: 0.5rem; color: #2c3e50; }
    .landing-subtitle { text-align: center; color: #7f8c8d; margin-bottom: 4rem; }
</style>
""", unsafe_allow_html=True)


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "platform" not in st.session_state:
    st.session_state.platform = "General"

if "page" not in st.session_state:
    st.session_state.page = "landing"

def set_platform(p_name):
    st.session_state.platform = p_name
    st.session_state.page = "chat"
    st.rerun()

def go_home():
    st.session_state.page = "landing"
    st.rerun()

# Platform configuration
PLATFORMS = {
    "IBM MQ": {"icon": "📬", "color": "#ff6b6b", "description": "IBM MQ - Queues, channels, managers"},
    "Splunk": {"icon": "🔍", "color": "#00c853", "description": "Log analysis and search"},
    "Redis": {"icon": "⚡", "color": "#ff9800", "description": "Cache status and memory"},
    "IBM ACE": {"icon": "🔗", "color": "#2196f3", "description": "IBM App Connect Enterprise"},
    "Apigee": {"icon": "🌐", "color": "#9c27b0", "description": "API Gateway monitoring"}
}

# ----------------- LANDING PAGE -----------------
if st.session_state.page == "landing":
    st.markdown('<h1 class="landing-title">🤖 Platform Support Bot</h1>', unsafe_allow_html=True)
    st.markdown('<p class="landing-subtitle">Choose a platform to start diagnosing</p>', unsafe_allow_html=True)
    
    st.markdown('<div class="tile-grid">', unsafe_allow_html=True)
    cols = st.columns(3)
    p_names = list(PLATFORMS.keys())
    for i, p_name in enumerate(p_names):
        with cols[i % 3]:
            if st.button(p_name, key=f"sel_{p_name}", use_container_width=True):
                set_platform(p_name)
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- CHAT PAGE -----------------
else:
    with st.sidebar:
        st.markdown("### 🤖 Platform Support Bot")
        if st.button("🏠 Back to Home", use_container_width=True):
            go_home()
        st.markdown("---")
        selected_platform = st.selectbox(
            "Change Platform",
            options=list(PLATFORMS.keys()),
            index=list(PLATFORMS.keys()).index(st.session_state.platform)
        )
        if selected_platform != st.session_state.platform:
            st.session_state.platform = selected_platform
        
        p_info = PLATFORMS[st.session_state.platform]
        st.markdown(f"""
        <div class="info-container">
            <div style="font-size: 2rem; text-align: center;">{p_info['icon']}</div>
            <div style="text-align: center; color: {p_info['color']}; font-weight: 600;">{st.session_state.platform}</div>
            <div style="font-size: 0.8rem; color: #7f8c8d; text-align: center;">{p_info['description']}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.markdown(f'<h2 style="margin-top: 0px;">{PLATFORMS[st.session_state.platform]["icon"]} {st.session_state.platform} Support</h2>', unsafe_allow_html=True)
    
    chat_container = st.container()
    with chat_container:
        for m in st.session_state.messages:
            role, content, p = m["role"], m["content"], m.get("platform", "General")
            if role == "user":
                st.markdown(f'''
                    <div class="chat-row user-row">
                        <div class="message-header" style="color: #3498db;">👤 YOU</div>
                        <div class="chat-bubble user-bubble">{content}</div>
                    </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                    <div class="chat-row bot-row">
                        <div class="message-header" style="color: #9b59b6;">
                            🤖 ASSISTANT <span class="platform-badge">{PLATFORMS[p]["icon"]} {p}</span>
                        </div>
                        <div class="chat-bubble bot-bubble">{content}</div>
                    </div>
                ''', unsafe_allow_html=True)

    # Input area - chat_input is natively pinned to the bottom
    prompt = st.chat_input(f"Ask about {st.session_state.platform}...")

    # Process user input
    if prompt:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "platform": st.session_state.platform
        })
        
        # Immediate rerun to show user message while thinking
        st.rerun()

    # If there's a new user message that needs a response
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        user_msg = st.session_state.messages[-1]["content"]
        
        with st.spinner(""):
            thinking_placeholder = st.empty()
            with thinking_placeholder.container():
                st.markdown('<div class="thinking">🤔 Thinking...</div>', unsafe_allow_html=True)
                try:
                    resp = asyncio.run(run_query(user_msg, st.session_state.platform))
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": resp, 
                        "platform": st.session_state.platform
                    })
                except Exception as e:
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"❌ Error: {str(e)}", 
                        "platform": st.session_state.platform
                    })
        st.rerun()

    if not st.session_state.messages:
        st.markdown(f'<div style="text-align: center; padding-top: 1rem; color: #7f8c8d;"><div style="font-size: 2.5rem;">{PLATFORMS[st.session_state.platform]["icon"]}</div><h3 style="margin-top: 0px;">Chat started with {st.session_state.platform}!</h3><p>How can I help you today?</p></div>', unsafe_allow_html=True)
