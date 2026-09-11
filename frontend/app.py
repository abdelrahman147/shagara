"""Official Streamlit frontend required by the course guide.

The React/Vite workspace is the richer presentation UI; this file keeps the
submission compatible with the documented Streamlit run command.
"""
import os
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="shagara — Rooftop Garden Intelligence", page_icon="🌿", layout="wide")
st.title("🌿 shagara")
st.caption("Rooftop knowledge, grounded in your garden documents")

if "messages" not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.write(f"{source['marker']} · {source['document']} · {source['section']}")
                    st.caption(source["excerpt"])

with st.sidebar:
    st.subheader("Garden documents")
    upload = st.file_uploader("Add PDF, Markdown, or text", type=["pdf", "md", "txt"])
    if upload and st.button("Index document"):
        with st.spinner("Parsing and indexing…"):
            response = requests.post(f"{API_BASE_URL}/documents/upload", files={"file": (upload.name, upload.getvalue())}, timeout=60)
        if response.ok:
            st.success(f"Indexed {upload.name}")
        else:
            st.error(response.text)
    st.caption(f"Backend: {API_BASE_URL}")

question = st.chat_input("Ask about irrigation, pests, compost, or harvest rules")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching grounded notes…"):
            try:
                response = requests.post(f"{API_BASE_URL}/query", json={"question": question, "tenant_id": "shagara", "access_levels": ["all", "members"]}, timeout=60)
                response.raise_for_status()
                data = response.json()
                answer = data["answer"]
                st.markdown(answer)
                if data.get("sources"):
                    with st.expander("Sources"):
                        for source in data["sources"]:
                            st.write(f"{source['marker']} · {source['document']} · {source['section']}")
                            st.caption(source["excerpt"])
                st.session_state.messages.append({"role": "assistant", "content": answer, "sources": data.get("sources", [])})
            except requests.RequestException:
                st.error("shagara could not reach the FastAPI backend. Start it on port 8000 and retry.")




