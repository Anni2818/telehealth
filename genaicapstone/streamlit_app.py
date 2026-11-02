import streamlit as st


st.set_page_config(
    page_title="CareConnect Assistant",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded",
)

WELCOME = (
    "Welcome to CareConnect. This is the chat-interface preview. "
    "The conversational backend is not connected yet, so I cannot "
    "answer FAQs, check availability, or create appointments."
)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": WELCOME}
    ]

with st.sidebar:
    st.title("💬 CareConnect")
    st.caption("AI appointment receptionist")

    if st.button(
        "＋ New chat",
        use_container_width=True,
        type="primary",
    ):
        st.session_state.messages = [
            {"role": "assistant", "content": WELCOME}
        ]
        st.rerun()

    st.divider()

    st.subheader("Project capabilities")
    st.caption(
        "Planned integrations, not available in this UI preview:"
    )
    st.markdown(
        "- Appointment search and booking\n"
        "- Cancellation and rescheduling\n"
        "- FAQ answers with source references\n"
        "- Safety escalation and human handoff"
    )

    st.divider()

    st.warning("UI preview · Agent not connected")

    st.caption(
        "Fictional educational platform. "
        "Use synthetic information only. "
        "Do not enter personal or medical details."
    )

    st.caption(
        "New chat clears this page's conversation state. "
        "History is not saved to the database."
    )

st.title("CareConnect")
st.caption("Your appointment assistant, one conversation at a time.")

st.info(
    "Frontend preview only. No AI service, FAQ retrieval, "
    "or appointment operation is connected."
)

st.caption(
    "Not for emergencies or medical advice. "
    "For an emergency, seek immediate local emergency care."
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

prompt = st.chat_input(
    "Type a synthetic test message...",
    max_chars=2000,
)

if prompt:
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.write(prompt)

    response = (
        "Your test message was received by the chat interface. "
        "The conversational backend is not connected yet. "
        "No FAQ search, availability check, or booking was performed."
    )

    with st.chat_message("assistant"):
        st.write(response)

    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )
