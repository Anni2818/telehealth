import hmac
import os

import streamlit as st


st.set_page_config(
    page_title="CareConnect",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded",
)

WELCOME = (
    "Welcome to CareConnect. The chat interface is ready, "
    "but the conversational agent is not connected yet. "
    "No FAQ search or appointment operation will be performed."
)


def reset_chat():
    st.session_state.messages = [
        {"role": "assistant", "content": WELCOME}
    ]


def logout():
    st.session_state.clear()
    st.rerun()


def check_login():
    username = st.session_state.get("login_username", "").strip()
    password = st.session_state.get("login_password", "")

    expected_user = os.environ.get("CARECONNECT_DEMO_USER", "")
    expected_password = os.environ.get("CARECONNECT_DEMO_PASSWORD", "")

    valid_user = hmac.compare_digest(
        username.encode(), expected_user.encode()
    )
    valid_password = hmac.compare_digest(
        password.encode(), expected_password.encode()
    )

    if expected_user and expected_password and valid_user and valid_password:
        st.session_state.authenticated = True
        st.session_state.display_name = username
        st.session_state.pop("login_error", None)
        reset_chat()
    else:
        st.session_state.login_error = "Invalid username or password."

    st.session_state.pop("login_password", None)


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.sidebar:
        st.title("💬 CareConnect")
        st.caption("AI appointment receptionist")
        st.divider()
        st.caption("Fictional educational platform.")
        st.warning("Demo login only")
        st.caption(
            "This login does not authorize access to appointment APIs "
            "or Azure SQL records."
        )

    st.title("Welcome to CareConnect")
    st.caption("Sign in to open your appointment assistant.")

    configured = bool(
        os.environ.get("CARECONNECT_DEMO_USER")
        and os.environ.get("CARECONNECT_DEMO_PASSWORD")
    )

    if not configured:
        st.error(
            "Demo credentials are not configured. "
            "Set CARECONNECT_DEMO_USER and CARECONNECT_DEMO_PASSWORD "
            "in the terminal before starting Streamlit."
        )
        st.stop()

    with st.form("login_form"):
        st.subheader("Sign in")
        st.text_input(
            "Username",
            key="login_username",
            max_chars=100,
        )
        st.text_input(
            "Password",
            type="password",
            key="login_password",
            max_chars=256,
        )
        st.form_submit_button(
            "Sign in",
            type="primary",
            use_container_width=True,
            on_click=check_login,
        )

    if "login_error" in st.session_state:
        st.error(st.session_state.login_error)

    st.caption(
        "Use demo credentials only. "
        "Do not enter a corporate or personal account password."
    )
    st.stop()


if "messages" not in st.session_state:
    reset_chat()

with st.sidebar:
    st.title("💬 CareConnect")
    st.caption("AI appointment receptionist")
    st.text(f"Signed in: {st.session_state.display_name}")

    if st.button(
        "＋ New chat",
        type="primary",
        use_container_width=True,
    ):
        reset_chat()
        st.rerun()

    st.divider()
    st.caption("Planned capabilities")
    st.markdown(
        "- Appointment navigation\n"
        "- Booking, cancellation and rescheduling\n"
        "- FAQ answers with citations\n"
        "- Human handoff"
    )

    st.divider()
    st.warning("UI preview · Agent not connected")
    st.caption(
        "Use synthetic information only. "
        "Do not enter personal or medical details."
    )
    st.caption(
        "Conversation history is session-only, "
        "not saved to Azure SQL."
    )

    if st.button("Log out", use_container_width=True):
        logout()

st.title("CareConnect")
st.caption("Your appointment assistant, one conversation at a time.")

st.info(
    "Frontend preview only. AI, FAQ retrieval and "
    "appointment operations are not connected."
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
        "Your test message was received by the interface. "
        "The conversational backend is not connected yet. "
        "No FAQ search, availability check or booking was performed."
    )

    with st.chat_message("assistant"):
        st.write(response)

    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )
