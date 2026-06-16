import streamlit as st

from qna.graph import build_qna_graph

st.title("MinuteMind")

if "company_id" not in st.session_state:
    st.session_state.company_id = "acme_internal"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "graph" not in st.session_state:
    st.session_state.graph = build_qna_graph()

company_id = st.sidebar.text_input("Company ID", value=st.session_state.company_id)
st.session_state.company_id = company_id

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
if prompt := st.chat_input("Ask about your meetings..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Run QnA graph
    result = st.session_state.graph.invoke(
        {
            "company_id": st.session_state.company_id,
            "chat_history": st.session_state.chat_history[:-1],  # history without current turn
            "latest_turn": prompt,
            "retry_count": 0,
        }
    )

    answer = result.get("final_answer", "Something went wrong.")
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.write(answer)
