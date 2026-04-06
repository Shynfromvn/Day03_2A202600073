import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Cấu hình giao diện Streamlit
st.set_page_config(page_title="Baseline Chatbot", page_icon="🤖")
st.title("🤖 Baseline Chatbot (OpenAI)")
st.markdown("Đây là phiên bản chatbot cơ bản để làm gốc so sánh với ReAct Agent.")

# Khởi tạo client OpenAI
@st.cache_resource
def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

client = get_openai_client()

# Khởi tạo session state để lưu trữ lịch sử chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "Bạn là trợ lý đặt vé xem phim."}
    ]

# Hiển thị lịch sử chat (bỏ qua tin nhắn hệ thống)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Xử lý input từ người dùng
if prompt := st.chat_input("Nhập yêu cầu của bạn (VD: Đặt 2 vé Zootopia 2 tại CGV HCM vào tối nay)..."):
    # Hiển thị tin nhắn user
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Lưu tin nhắn của user vào history
    st.session_state.messages.append({"role": "user", "content": prompt})
        
    # Gọi API OpenAI để nhận phản hồi
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("AI đang suy nghĩ..."):
            try:
                # Gọi model gpt-4o-mini để xử lý (đã sửa lỗi gpt-5.4-mini ở bản cũ)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=st.session_state.messages
                )
                
                answer = response.choices[0].message.content
                message_placeholder.markdown(answer)
                
                # Lưu phản hồi vào history
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                st.error(f"Lỗi rồi: {e}")