import json
import streamlit as st
import requests
from datetime import datetime

LAMBDA_URL = "https://gij3liro3kouweizzludyyhbe40dsxcw.lambda-url.us-east-1.on.aws"
LOCAL_URL = "http://localhost:8000"

# Toggle: set to LOCAL_URL for local dev, LAMBDA_URL for production
API_URL = LAMBDA_URL

# Streaming only works with local uvicorn (Mangum/Lambda doesn't support SSE)
USE_STREAMING = API_URL == LOCAL_URL

st.set_page_config(
    page_title="Qorpy",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="auto"
)


# ── API Function ───────────────────────────────────────────────────────────────

def create_session() -> str | None:
    """Call /create-session and return a new session_id, or None on failure."""
    try:
        r = requests.post(f"{API_URL}/create-session", timeout=15)
        data = r.json()
        if data.get("responseCode") == "00":
            return data["data"]["session_id"]
    except Exception:
        pass
    return None


def ask_question(question: str, session_id: str | None = None) -> str:
    """Non-streaming fallback — used for suggestion chips."""
    try:
        payload = {"question": question}
        if session_id:
            payload["session_id"] = session_id
        response = requests.post(
            f"{API_URL}/ask-question",
            json=payload,
            timeout=60
        )
        data = response.json()
        if data.get("responseCode") == "00":
            result = data.get("data", {})
            return result.get("answer") or result.get("response") or str(result)
        return f"⚠️ {data.get('responseMessage', 'Something went wrong')}"
    except requests.exceptions.Timeout:
        return "⏱️ Request timed out. Please try again."
    except Exception as e:
        return f"❌ Connection error: {str(e)}"


def ask_question_stream(question: str, session_id: str | None = None):
    """Generator that yields answer text chunks from the SSE streaming endpoint."""
    try:
        payload = {"question": question}
        if session_id:
            payload["session_id"] = session_id
        with requests.post(
            f"{API_URL}/ask-question-stream",
            json=payload,
            stream=True,
            timeout=60
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    text = chunk.get("text", "")
                    if text:
                        yield text
                except json.JSONDecodeError:
                    continue
    except requests.exceptions.Timeout:
        yield "\n\n⏱️ Request timed out. Please try again."
    except Exception as e:
        yield f"\n\n❌ Connection error: {str(e)}"

# ── Session State Management ──────────────────────────────────────────────────

if "conversations" not in st.session_state:
    st.session_state.conversations = {}
    
if "active_id" not in st.session_state:
    st.session_state.active_id = None

def create_new_chat():
    cid = datetime.now().strftime("%Y%m%d%H%M%S%f")
    st.session_state.conversations[cid] = {
        "title": "New conversation",
        "messages": [],
        "timestamp": datetime.now(),
        "session_id": None,  # assigned when user clicks Start Session
    }
    st.session_state.active_id = cid
    return cid

# Initialize first conversation if none exists
if not st.session_state.conversations:
    create_new_chat()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Qorpy")

    # New Chat Button
    if st.button("＋ New Chat", type="secondary", use_container_width=True):
        create_new_chat()
        st.rerun()

    # Admin Page Button
    if st.button("⚙️ Admin Panel", type="secondary", use_container_width=True):
        st.switch_page("pages/admin.py")

    # ── Session Management ──────────────────────────────────────────────
    st.markdown("**Session**")

    _active_sid = st.session_state.conversations.get(
        st.session_state.active_id, {}
    ).get("session_id")

    if _active_sid:
        st.caption(f"Active session: {_active_sid[:18]}...")
        if st.button("↺ New Session", type="secondary", use_container_width=True, key="new_session_btn"):
            new_sid = create_session()
            if new_sid:
                st.session_state.conversations[st.session_state.active_id]["session_id"] = new_sid
                st.success("New session started")
                st.rerun()
            else:
                st.error("Failed to create session")
    else:
        st.caption("No active session")
        if st.button("▶ Start Session", type="primary", use_container_width=True, key="start_session_btn"):
            new_sid = create_session()
            if new_sid:
                st.session_state.conversations[st.session_state.active_id]["session_id"] = new_sid
                st.rerun()
            else:
                st.error("Could not reach the API — try again")

    # History Section
    if st.session_state.conversations:
        st.markdown("**Recent chats**")
        
        # Sort by timestamp, newest first
        sorted_convs = sorted(
            st.session_state.conversations.items(),
            key=lambda x: x[1].get("timestamp", datetime.min),
            reverse=True
        )
        
        for cid, conv in sorted_convs:
            title = conv["title"]
            is_active = cid == st.session_state.active_id
            
            # Use columns for better click handling
            cols = st.columns([1])
            with cols[0]:
                if st.button(
                    f"{'● ' if is_active else '○ '} {title[:25]}{'...' if len(title) > 25 else ''}",
                    key=f"hist_{cid}",
                    help="Click to open conversation",
                    use_container_width=True,
                    type="secondary" if not is_active else "primary"
                ):
                    st.session_state.active_id = cid
                    st.rerun()

# ── Main Chat Interface ────────────────────────────────────────────────────────

st.title("Qorpy FAQ")

active_conv = st.session_state.conversations[st.session_state.active_id]
messages = active_conv["messages"]

# Welcome State (when no messages)
if not messages:
    st.markdown("## ✨ How can I help you today?")
    st.caption("Ask me anything about Qorpy — products, pricing, getting started, or troubleshooting.")
    st.write("")

    suggestions = [
        "What is Qorpy?",
        "How do I get started?",
        "What are pricing plans?",
        "How does billing work?",
        "Can I cancel anytime?",
        "Contact support"
    ]
    
    # Create grid of suggestion buttons
    suggestion_cols = st.columns(3)
    for i, suggestion in enumerate(suggestions):
        with suggestion_cols[i % 3]:
            if st.button(suggestion, key=f"sugg_{i}", use_container_width=True, type="secondary"):
                messages.append({"role": "user", "content": suggestion})
                active_conv["title"] = suggestion[:40]
                with st.spinner(""):
                    answer = ask_question(suggestion, session_id=active_conv.get("session_id"))
                messages.append({"role": "assistant", "content": answer})
                st.rerun()

else:
    # Chat header showing conversation title
    st.caption(f"{active_conv['title']} · {len(messages)//2} messages")

    # Display existing messages
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── Chat Input ─────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Message Qorpy...", key="chat_input"):
    # Deduplicate: skip if this exact prompt was already processed this session
    if st.session_state.get("_last_prompt") == prompt:
        st.stop()
    st.session_state["_last_prompt"] = prompt

    # Add user message
    messages.append({"role": "user", "content": prompt})
    
    # Update conversation title on first message
    if len(messages) == 1:
        active_conv["title"] = prompt[:40] + ("..." if len(prompt) > 40 else "")
    
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Stream or block depending on deployment target
    _sid = active_conv.get("session_id")
    with st.chat_message("assistant"):
        if USE_STREAMING:
            answer = st.write_stream(ask_question_stream(prompt, session_id=_sid))
        else:
            with st.spinner("Thinking..."):
                answer = ask_question(prompt, session_id=_sid)
            st.markdown(answer)

    # Save assistant message
    messages.append({"role": "assistant", "content": answer})
    
    # Clear dedup key then rerun to commit messages to history
    st.session_state["_last_prompt"] = None
    st.rerun()