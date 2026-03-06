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
    initial_sidebar_state="auto",
)


st.title("Qorpy Admin")

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
                        st.success("Added successfully")
                    else:
                        st.error(f"Error: {data.get('responseMessage', 'Error')}")
                except Exception as e:
                    st.error(f"Connection error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Search & Edit
# ═══════════════════════════════════════════════════════════════════════════════
with tab_search:
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

        st.markdown(f"**Match {idx+1}** · {score_pct}% relevance · {category}")
        st.markdown(f"**Q:** {match['question']}")
        st.markdown(f"**A:** {match['answer']}")
        st.divider()

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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Bulk Upload
# ═══════════════════════════════════════════════════════════════════════════════
with tab_bulk:
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
                st.caption(f"Preview (first {len(preview_rows)} rows)")
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
                    st.success(f"Successfully added {count} Q&A pairs")
                else:
                    st.error(f"Error: {data.get('responseMessage', 'Error')}")
            except Exception as e:
                st.error(f"Connection error: {e}")

