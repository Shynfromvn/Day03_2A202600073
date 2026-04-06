import streamlit as st
import os
from dotenv import load_dotenv

# Ensure the src module can be found if running from the root dictionary
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.agent.agent import ReActAgent
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.core.local_provider import LocalProvider
from src.tools.movie_booking_tools import get_tools

load_dotenv()

st.set_page_config(
    page_title="Cinemagic | ReAct Agent", 
    page_icon="🍿", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Premium UI ---
st.markdown("""
<style>
    /* General styles */
    .stApp {
        /* let config.toml handle background */
    }
    
    /* Gradient Text */
    .gradient-text {
        background: linear-gradient(90deg, #F59E0B, #EF4444);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.8rem;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    
    /* Header margins */
    .header-subtext {
        color: #9CA3AF;
        font-size: 1.1rem;
        margin-top: -10px;
        margin-bottom: 20px;
    }

    /* Sidebar tweaks */
    [data-testid="stSidebar"] {
        border-right: 1px solid #30363D;
    }
    
    /* Chat input styling */
    .stChatInput {
        border-radius: 12px !important;
    }
    
    /* Button hover animations */
    .stButton>button {
        border-radius: 8px;
        border: 1px solid #30363D;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        border-color: #EF4444;
        color: #EF4444;
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- Header Section ---
col1, col2 = st.columns([1, 8])
with col1:
    st.image("https://cdn-icons-png.flaticon.com/512/3418/3418886.png", width=80)
with col2:
    st.markdown('<p class="gradient-text">Cinemagic ReAct Agent</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-subtext">AI Assistant powered by Thought-Action-Observation framework.</p>', unsafe_allow_html=True)

st.divider()

# --- Sidebar Configuration ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/863/863684.png", width=60)
    st.title("⚙️ System Control")
    
    provider_choice = st.selectbox(
        "🧠 Chọn LLM Provider",
        (
            "OpenAI / GitHub Models (gpt-4o)", 
            "Google Gemini (gemini-2.0-flash)",
            "Local Phi-3 (chỉ khả dụng khi chạy local)"
        )
    )
    
    st.divider()
    with st.expander("ℹ️ Hướng dẫn sử dụng", expanded=True):
        st.markdown(
            "Chào mừng bạn đến với Cinemagic! \n"
            "Hãy yêu cầu AI thực hiện các tác vụ khó như:\n\n"
            "- Tìm phim hành động đang chiếu\n"
            "- Xem rạp nào hỗ trợ xem Dune 2\n"
            "- Đặt 2 vé xem phim ngày hôm nay\n"
            "- Tìm khuyến mãi sinh viên rẻ nhất"
        )
        
    st.divider()
    if st.button("🗑️ Xóa Lịch Sử Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- Initialize Agent ---
@st.cache_resource(show_spinner=False)
def get_agent(provider_type):
    if "Google" in provider_type:
        llm = GeminiProvider(model_name="gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))
    elif "Local" in provider_type:
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        try:
            llm = LocalProvider(model_path=model_path, n_ctx=2048)
        except Exception as e:
            st.error(f"Lỗi khi load Local model: {e}")
            llm = OpenAIProvider(model_name="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
    else:
        llm = OpenAIProvider(model_name="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
    return ReActAgent(llm=llm, tools=get_tools(), max_steps=6)

agent = get_agent(provider_choice)

# --- Chat Interface ---
if "messages" not in st.session_state or len(st.session_state.messages) == 0:
    st.session_state.messages = []
    # Lời chào ban đầu
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Xin chào! 👋 Tôi là trợ lý rạp chiếu phim **Cinemagic**. Tôi có thể giúp bạn tìm lịch chiếu, chọn rạp và đặt mức giá ưu đãi nhất. Bạn muốn xem phim gì hôm nay?"
    })

# Render history
for message in st.session_state.messages:
    # Chọn avatar xịn xò
    avatar = "🍿" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("VD: Đặt 2 vé phim hành động ở CGV gần đây..."):
    # Hạn chế chat khi input rỗng
    if prompt.strip():
        # Render user message
        st.chat_message("user", avatar="👤").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Render assistant response with spinner
        with st.chat_message("assistant", avatar="🍿"):
            with st.spinner("Đang suy luận (ReAct loop)..."):
                try:
                    response = agent.run(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = f"**Lỗi Hệ Thống:** {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
