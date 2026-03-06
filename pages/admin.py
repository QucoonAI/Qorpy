"""
Qorpy Admin — Manage FAQ Knowledge Base
========================================
• Add a single Q&A pair
• Search & edit existing answers
• Bulk upload Q&A from Excel (.xlsx)
"""

import json
import streamlit as st
import requests
from io import BytesIO

# ── Config ─────────────────────────────────────────────────────────────────────

LAMBDA_URL = "https://gij3liro3kouweizzludyyhbe40dsxcw.lambda-url.us-east-1.on.aws"
LOCAL_URL = "http://localhost:8000"
API_URL = LAMBDA_URL

st.set_page_config(
    page_title="Qorpy Admin",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    #MainMenu, header, footer, .stDeployButton { visibility: hidden; display: none !important; }

    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #fafafa 0%, #f5f5f5 100%);
    }
    [data-testid="stMain"] { background: transparent; max-width: 900px; margin: 0 auto; }
    .block-container { padding: 0 1rem 2rem 1rem !important; max-width: 850px !important; padding-top: 80px !important; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #111111 !important; border-right: 1px solid #222 !important; }

    /* Force ALL body text to be dark/readable */
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .block-container,
    .stMarkdown, .stMarkdown p, .stMarkdown span,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    p, span, label, div {
        color: #111111 !important;
    }

    /* Tab labels */
    [data-testid="stTabs"] button[role="tab"] p,
    [data-testid="stTabs"] button[role="tab"] {
        color: #111111 !important;
    }

    /* Form labels */
    [data-testid="stTextInput"] label,
    [data-testid="stTextArea"] label,
    [data-testid="stFileUploader"] label,
    .stForm label {
        color: #111111 !important;
        font-weight: 500 !important;
    }

    /* Input & textarea text */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        color: #111111 !important;
        background: #ffffff !important;
    }

    /* Caption / subtext */
    [data-testid="stCaptionContainer"] p,
    .stCaption, small {
        color: #666666 !important;
    }

    /* Expander header */
    [data-testid="stExpander"] summary p {
        color: #111111 !important;
    }

    /* Cards */
    .admin-card {
        background: #ffffff;
        border: 1px solid #e5e5e5;
        border-radius: 14px;
        padding: 1.75rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .admin-card h3 { margin-top: 0; color: #111111 !important; }

    /* Section label */
    .section-label {
        font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.1em; color: #888; margin-bottom: 0.5rem;
    }

    /* Status badge */
    .badge-ok  { display: inline-block; background: #d4edda; color: #155724; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 500; }
    .badge-err { display: inline-block; background: #f8d7da; color: #721c24; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 500; }

    /* Result card */
    .result-card {
        background: #f9f9f9;
        border: 1px solid #eee;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .result-card .score    { font-size: 12px; color: #888; }
    .result-card .question { font-weight: 600; color: #111111; margin: 4px 0; }
    .result-card .answer   { color: #444444; font-size: 14px; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ── Fixed Header ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
    background: #ffffff; font-family: 'Inter', sans-serif;
    font-size: 18px; font-weight: 800; color: #111111;
    letter-spacing: 0.08em; padding: 1rem 2rem;
    border-bottom: 2px solid #111111; text-transform: uppercase;
    display: flex; justify-content: space-between; align-items: center;
">
    <span>QORPY ADMIN</span>
</div>
""", unsafe_allow_html=True)

# ── Navigation ─────────────────────────────────────────────────────────────────
col_nav1, col_nav2 = st.columns([6, 1])
with col_nav2:
    if st.button("← Chat", use_container_width=True, type="secondary"):
        st.switch_page("chat.py")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_add, tab_search, tab_bulk = st.tabs(["➕ Add Q&A", "🔍 Search & Edit", "📤 Bulk Upload"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Add Single Q&A
# ═══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.markdown('<div class="admin-card">', unsafe_allow_html=True)
    st.markdown("### Add a Q&A Pair")
    st.caption("The question and answer will be embedded and stored in Pinecone immediately.")

    with st.form("add_qa_form", clear_on_submit=True):
        qa_question = st.text_input("Question", placeholder="e.g. How do I generate an e-Invoice?")
        qa_answer = st.text_area("Answer", height=150, placeholder="Detailed answer…")
        col1, col2 = st.columns(2)
        with col1:
            qa_category = st.text_input("Category (optional)", value="General")
        with col2:
            qa_section = st.text_input("Section (optional)", value="General")

        submitted = st.form_submit_button("Add to Knowledge Base", type="primary", use_container_width=True)

    if submitted:
        if not qa_question.strip() or not qa_answer.strip():
            st.warning("Both question and answer are required.")
        else:
            with st.spinner("Embedding & uploading…"):
                try:
                    resp = requests.post(
                        f"{API_URL}/add-qa",
                        json={
                            "question": qa_question.strip(),
                            "answer": qa_answer.strip(),
                            "category": qa_category.strip(),
                            "section": qa_section.strip(),
                        },
                        timeout=30,
                    )
                    data = resp.json()
                    if data.get("responseCode") == "00":
                        st.markdown('<span class="badge-ok">✓ Added successfully</span>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<span class="badge-err">✗ {data.get("responseMessage", "Error")}</span>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Connection error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Search & Edit
# ═══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.markdown('<div class="admin-card">', unsafe_allow_html=True)
    st.markdown("### Search & Edit Existing Q&A")
    st.caption("Type a question exactly as a user would ask it. The top 3 closest matching Q&A pairs will appear with their current answers — click **Edit** to update any of them.")

    search_query = st.text_input(
        "Question",
        key="search_q",
        placeholder="e.g. How do I generate an e-Invoice?",
        label_visibility="collapsed",
    )
    search_btn = st.button("🔍 Find Matching Q&A", type="primary", use_container_width=True, key="search_btn")

    # Keep results in session state so they persist across edits
    if "search_results" not in st.session_state:
        st.session_state.search_results = []

    if search_btn and search_query.strip():
        with st.spinner("Finding closest matches…"):
            try:
                resp = requests.post(
                    f"{API_URL}/search-qa",
                    json={"query": search_query.strip(), "top_k": 3},
                    timeout=30,
                )
                data = resp.json()
                if data.get("responseCode") == "00":
                    st.session_state.search_results = data["data"]["matches"]
                else:
                    st.warning(data.get("responseMessage", "Search failed"))
                    st.session_state.search_results = []
            except Exception as e:
                st.error(f"Connection error: {e}")
                st.session_state.search_results = []

    # Display results — show full Q&A, edit inline
    for idx, match in enumerate(st.session_state.search_results):
        score_pct = int(match['score'] * 100)
        category = match.get('category', '') or 'General'

        st.markdown(f"""
        <div class="result-card">
            <span class="score">Match {idx+1} &nbsp;·&nbsp; {score_pct}% relevance &nbsp;·&nbsp; {category}</span>
            <div class="question">Q: {match['question']}</div>
            <div class="answer">A: {match['answer']}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"✏️ Edit this answer", expanded=False):
            new_q = st.text_input(
                "Question",
                value=match["question"],
                key=f"edit_q_{idx}",
            )
            new_a = st.text_area(
                "Answer",
                value=match["answer"],
                height=180,
                key=f"edit_a_{idx}",
                help="Edit the answer then click Update — it will be re-embedded and saved to Pinecone.",
            )
            if st.button("Update", key=f"update_btn_{idx}", type="primary", use_container_width=True):
                with st.spinner("Re-embedding and saving…"):
                    try:
                        payload = {
                            "vector_id": match["id"],
                            "new_answer": new_a.strip(),
                        }
                        if new_q.strip() != match["question"]:
                            payload["new_question"] = new_q.strip()

                        resp = requests.post(
                            f"{API_URL}/update-qa",
                            json=payload,
                            timeout=30,
                        )
                        data = resp.json()
                        if data.get("responseCode") == "00":
                            st.success("✓ Updated — the chatbot will use the new answer immediately.")
                            st.session_state.search_results[idx]["answer"] = new_a.strip()
                            if new_q.strip() != match["question"]:
                                st.session_state.search_results[idx]["question"] = new_q.strip()
                        else:
                            st.error(data.get("responseMessage", "Update failed"))
                    except Exception as e:
                        st.error(f"Connection error: {e}")

    if not st.session_state.search_results and search_btn:
        st.info("No results found. Try a different search query.")

    st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Bulk Upload
# ═══════════════════════════════════════════════════════════════════════════════
with tab_bulk:
    st.markdown('<div class="admin-card">', unsafe_allow_html=True)
    st.markdown("### Bulk Upload from Excel")
    st.caption("Upload a `.xlsx` file with **Question** in column A and **Answer** in column B. The first row is treated as a header and skipped.")

    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"], key="bulk_file")

    col1, col2 = st.columns(2)
    with col1:
        bulk_category = st.text_input("Category", value="General", key="bulk_cat")
    with col2:
        bulk_section = st.text_input("Section", value="General", key="bulk_sec")

    # Preview
    if uploaded_file is not None:
        try:
            import openpyxl

            wb = openpyxl.load_workbook(BytesIO(uploaded_file.getvalue()), read_only=True)
            ws = wb.active
            preview_rows = []
            for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                q = str(row[0]).strip() if row[0] else ""
                a = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                if q and a:
                    preview_rows.append({"Question": q, "Answer": a[:120] + ("…" if len(a) > 120 else "")})
                if len(preview_rows) >= 5:
                    break
            wb.close()

            if preview_rows:
                st.markdown(f'<p class="section-label">Preview (first {len(preview_rows)} rows)</p>', unsafe_allow_html=True)
                st.dataframe(preview_rows, use_container_width=True, hide_index=True)
            else:
                st.warning("No valid Q&A pairs found in the file.")
        except Exception as e:
            st.error(f"Could not preview file: {e}")

    upload_btn = st.button("Upload & Add All", type="primary", use_container_width=True, key="bulk_upload_btn",
                           disabled=uploaded_file is None)

    if upload_btn and uploaded_file is not None:
        with st.spinner("Uploading & embedding all Q&A pairs…"):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                form_data = {"category": bulk_category.strip(), "section": bulk_section.strip()}
                resp = requests.post(
                    f"{API_URL}/bulk-add-qa",
                    files=files,
                    data=form_data,
                    timeout=120,
                )
                data = resp.json()
                if data.get("responseCode") == "00":
                    count = data.get("data", {}).get("pairs_added", 0)
                    st.markdown(f'<span class="badge-ok">✓ Successfully added {count} Q&A pairs</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="badge-err">✗ {data.get("responseMessage", "Error")}</span>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Connection error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
