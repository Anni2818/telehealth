import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import streamlit as st
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")

API_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000",
).strip().rstrip("/")

IST = ZoneInfo("Asia/Kolkata")


st.set_page_config(
    page_title="CareConnect AI",
    page_icon="✚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>

    .stApp {
        background: #F5F8FC;
        color: #172B4D;
    }

    .block-container {
        max-width: 1100px;
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }

    h1, h2, h3 {
        color: #172B4D;
        font-family: "Segoe UI", sans-serif;
        font-weight: 700;
    }

    p {
        line-height: 1.65;
    }

    /* Sidebar */

    [data-testid="stSidebar"] {
        background: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #172B4D;
    }

    /* Input fields */

    div[data-baseweb="input"] {
        background: #FFFFFF !important;
        border-radius: 10px !important;
    }

    div[data-baseweb="input"] input {
        background: #FFFFFF !important;
        color: #172B4D !important;
        -webkit-text-fill-color: #172B4D !important;
        caret-color: #087F8C !important;
    }

    div[data-baseweb="input"] input::placeholder {
        color: #718096 !important;
        -webkit-text-fill-color: #718096 !important;
    }

    /* Chat input */

    [data-testid="stChatInput"] {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 14px !important;
    }

    [data-testid="stChatInput"] textarea {
        background: #FFFFFF !important;
        color: #172B4D !important;
        -webkit-text-fill-color: #172B4D !important;
        caret-color: #087F8C !important;
        font-size: 15px !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #718096 !important;
        -webkit-text-fill-color: #718096 !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        outline: none !important;
    }

    /* Chat messages */

    [data-testid="stChatMessage"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(20, 40, 80, 0.035);
    }

    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li {
        color: #172B4D !important;
    }

    /* Buttons */

    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 42px;
    }

    div.stButton > button[kind="primary"] {
        background: #087F8C;
        color: #FFFFFF;
        border: none;
    }

    div.stButton > button[kind="primary"]:hover {
        background: #066873;
        color: #FFFFFF;
    }

    /* Hero */

    .hero {
        background: linear-gradient(
            115deg,
            #0D6474,
            #138B96
        );
        border-radius: 18px;
        padding: 30px 34px;
        margin-bottom: 25px;
        box-shadow: 0 8px 25px rgba(13, 100, 116, 0.12);
    }

    .hero-title {
        font-size: 30px;
        font-weight: 750;
        color: #FFFFFF;
        margin-bottom: 10px;
    }

    .hero-subtitle {
        font-size: 15px;
        color: #E5F7F8;
        line-height: 1.7;
    }

    /* Booking card */

    .booking-card {
        background: #FFFFFF;
        border: 1px solid #D7E7EA;
        border-left: 5px solid #087F8C;
        border-radius: 14px;
        padding: 22px;
        margin-top: 20px;
        margin-bottom: 18px;
        box-shadow: 0 5px 18px rgba(20, 60, 80, 0.05);
    }

    .booking-heading {
        color: #172B4D;
        font-size: 21px;
        font-weight: 700;
        margin-bottom: 12px;
    }

    .booking-status {
        display: inline-block;
        background: #FFF4D6;
        color: #926500;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 14px;
    }

    .booking-detail {
        color: #425466;
        font-size: 15px;
        margin-bottom: 8px;
    }

    /* Footer */

    .app-footer {
        text-align: center;
        color: #718096;
        font-size: 12px;
        margin-top: 35px;
        padding-top: 18px;
        border-top: 1px solid #E2E8F0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# API CLIENT
# --------------------------------------------------

class ApiError(Exception):

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def api_request(method, path, token=None, payload=None):

    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with httpx.Client(
            timeout=httpx.Timeout(
                180.0,
                connect=10.0,
            ),
            follow_redirects=False,
        ) as client:

            response = client.request(
                method=method,
                url=f"{API_URL}{path}",
                headers=headers,
                json=payload,
            )

    except httpx.TimeoutException as error:
        raise ApiError(
            "Request timed out. The operation may have reached "
            "the backend. Do not automatically retry."
        ) from error

    except httpx.RequestError as error:
        raise ApiError(
            "Cannot connect to FastAPI. Check the backend server."
        ) from error

    if not response.is_success:

        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None

        if not isinstance(detail, str):
            detail = f"Backend returned HTTP {response.status_code}"

        raise ApiError(
            detail,
            status_code=response.status_code,
        )

    try:
        return response.json()

    except ValueError as error:
        raise ApiError(
            "Invalid response received from backend."
        ) from error


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

def initialize_state():

    defaults = {
        "token": None,
        "customer": None,
        "sql_session_id": None,
        "messages": [],
        "pending_action": None,
        "chat_blocked": False,
        "execution_uncertain": False,
        "notice": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_login():

    st.session_state.token = None
    st.session_state.customer = None
    st.session_state.sql_session_id = None
    st.session_state.messages = []
    st.session_state.pending_action = None
    st.session_state.chat_blocked = False
    st.session_state.execution_uncertain = False


def handle_error(error):

    if error.status_code == 401:

        clear_login()

        st.session_state.notice = (
            "Your login has expired. Please sign in again."
        )

        st.rerun()

    st.error(str(error))


# --------------------------------------------------
# SESSION OPERATIONS
# --------------------------------------------------

def create_session():

    result = api_request(
        "POST",
        "/sessions",
        token=st.session_state.token,
    )

    st.session_state.sql_session_id = result["session_id"]
    st.session_state.messages = []
    st.session_state.pending_action = None
    st.session_state.chat_blocked = False
    st.session_state.execution_uncertain = False


def refresh_pending_action():

    session_id = st.session_state.sql_session_id

    if not session_id:
        return

    result = api_request(
        "GET",
        f"/actions/pending/{session_id}",
        token=st.session_state.token,
    )

    st.session_state.pending_action = result.get("action")


def format_local_time(value):

    if not value:
        return "Not available"

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            return value

        return parsed.astimezone(IST).strftime(
            "%d %B %Y, %I:%M %p IST"
        )

    except ValueError:
        return "Not available"


# --------------------------------------------------
# LOGIN PAGE
# --------------------------------------------------

def render_login():

    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">
                CareConnect AI
            </div>
            <div class="hero-subtitle">
                Your intelligent healthcare receptionist.
                Find appointments and manage your healthcare
                journey through natural conversation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.4, 1])

    with center:

        st.markdown("## Welcome back")

        st.caption(
            "Sign in using your registered account."
        )

        if st.session_state.notice:
            st.info(st.session_state.notice)
            st.session_state.notice = None

        with st.form("login_form"):

            username = st.text_input(
                "Username",
                placeholder="Enter your username",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            submitted = st.form_submit_button(
                "Sign in",
                type="primary",
                use_container_width=True,
            )

        if submitted:

            if not username.strip() or not password:
                st.error(
                    "Please enter your username and password."
                )
                return

            try:

                with st.spinner("Signing you in..."):

                    login = api_request(
                        "POST",
                        "/auth/login",
                        payload={
                            "username": username.strip(),
                            "password": password,
                        },
                    )

                    token = login["access_token"]

                    customer = api_request(
                        "GET",
                        "/auth/me",
                        token=token,
                    )

                st.session_state.token = token
                st.session_state.customer = customer

                st.rerun()

            except ApiError as error:
                st.error(str(error))


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

def render_sidebar():

    customer = st.session_state.customer

    with st.sidebar:

        st.title("CareConnect AI")

        st.caption(
            "Intelligent Telehealth Assistant"
        )

        st.divider()

        st.markdown("### Account")

        st.write(
            f"**{customer['username']}**"
        )

        st.caption(
            f"Customer: {customer['customer_code']}"
        )

        st.divider()

        st.markdown("### Conversation")

        if st.button(
            "New conversation",
            use_container_width=True,
        ):

            try:
                create_session()
                st.rerun()

            except ApiError as error:
                handle_error(error)

        if st.session_state.sql_session_id:
            st.success("Session active")

        st.divider()

        st.markdown("### Quick information")

        st.caption(
            "Search doctor availability and prepare "
            "appointments through the AI assistant."
        )

        st.divider()

        if st.button(
            "Sign out",
            use_container_width=True,
        ):

            session_id = st.session_state.sql_session_id

            if session_id:

                try:
                    api_request(
                        "POST",
                        f"/sessions/{session_id}/close",
                        token=st.session_state.token,
                    )

                except ApiError:
                    pass

            clear_login()
            st.rerun()

        st.caption(
            "Capstone demonstration using synthetic data."
        )


# --------------------------------------------------
# BOOKING CONFIRMATION
# --------------------------------------------------

def render_booking_confirmation(action):

    if action.get("action_type") != "BOOK":
        return

    st.markdown(
        """
        <div class="booking-card">
            <div class="booking-status">
                AWAITING CONFIRMATION
            </div>
            <div class="booking-heading">
                Review your appointment
            </div>
            <div class="booking-detail">
                Please verify the appointment details below.
                Your slot is not reserved until booking succeeds.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("**Doctor**")
        st.write(
            action.get("display_name") or "Not available"
        )

        st.markdown("**Specialty**")
        st.write(
            action.get("specialty_name") or "Not available"
        )

        st.markdown("**Location**")
        st.write(
            action.get("city") or "Not available"
        )

    with col2:

        st.markdown("**Appointment starts**")
        st.write(
            format_local_time(
                action.get("starts_at_local")
            )
        )

        st.markdown("**Appointment ends**")
        st.write(
            format_local_time(
                action.get("ends_at_local")
            )
        )

        st.markdown("**Slot ID**")
        st.write(
            action.get("selected_slot_id")
        )

    st.caption(
        "Confirmation deadline: "
        + format_local_time(
            action.get("expires_at_utc")
        )
    )

    if st.session_state.execution_uncertain:

        st.error(
            "The previous booking result is uncertain. "
            "Please check the backend before retrying."
        )

        return

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:

        if st.button(
            "Confirm booking",
            type="primary",
            use_container_width=True,
        ):

            execute_booking(action)

    with cancel_col:

        if st.button(
            "Not now",
            use_container_width=True,
        ):

            st.info(
                "Booking was not executed. "
                "The pending action remains in SQL until "
                "it expires or is superseded."
            )


def execute_booking(action):

    try:

        with st.spinner("Confirming appointment..."):

            result = api_request(
                "POST",
                "/actions/bookings/execute",
                token=st.session_state.token,
                payload={
                    "session_id": (
                        st.session_state.sql_session_id
                    ),
                    "action_id": action["action_id"],
                    "confirmed": True,
                },
            )

        appointment_id = result["appointment_id"]

        st.session_state.pending_action = None
        st.session_state.execution_uncertain = False

        if result.get("already_processed"):

            reply = (
                f"Appointment {appointment_id} was already "
                "processed. No duplicate booking was created."
            )

        else:

            reply = (
                f"Your appointment is confirmed. "
                f"Appointment ID: {appointment_id}."
            )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": reply,
                "tool_calls": [],
            }
        )

        st.session_state.notice = reply

        st.rerun()

    except ApiError as error:

        if error.status_code is None or error.status_code >= 500:
            st.session_state.execution_uncertain = True

        handle_error(error)


# --------------------------------------------------
# CHAT
# --------------------------------------------------

def process_message(message):

    st.session_state.messages.append(
        {
            "role": "user",
            "content": message,
            "tool_calls": [],
        }
    )

    try:

        with st.spinner("Assistant is responding..."):

            response = api_request(
                "POST",
                "/chat",
                token=st.session_state.token,
                payload={
                    "session_id": (
                        st.session_state.sql_session_id
                    ),
                    "message": message,
                },
            )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response["reply"],
                "tool_calls": response.get(
                    "tool_calls",
                    [],
                ),
            }
        )

        refresh_pending_action()

        st.rerun()

    except ApiError as error:

        st.session_state.chat_blocked = True
        handle_error(error)


def render_chat():

    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">
                Your AI Healthcare Receptionist
            </div>
            <div class="hero-subtitle">
                Search available appointments, explore doctors
                and prepare bookings through natural conversation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.notice:

        st.success(st.session_state.notice)
        st.session_state.notice = None

    if not st.session_state.messages:

        st.markdown("### Start with a question")

        st.info(
            "Try asking: Find dermatology appointments "
            "in Pune tomorrow."
        )

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message.get("tool_calls"):

                with st.expander("Tool activity"):
                    st.json(message["tool_calls"])

    action = st.session_state.pending_action

    if action:

        if action.get("action_type") == "BOOK":
            render_booking_confirmation(action)

        else:
            st.info(
                "A pending action exists. "
                "Booking confirmation is currently "
                "the only action connected to this UI."
            )

    if st.session_state.chat_blocked:

        st.warning(
            "This conversation is paused after an error. "
            "Start a new conversation or inspect the backend."
        )

    prompt = st.chat_input(
        "Type your message here...",
        max_chars=4000,
        disabled=(
            st.session_state.chat_blocked
            or st.session_state.execution_uncertain
            or st.session_state.pending_action is not None
        ),
    )

    if prompt and prompt.strip():
        process_message(prompt.strip())


# --------------------------------------------------
# APPLICATION
# --------------------------------------------------

initialize_state()

if not st.session_state.token:

    render_login()
    st.stop()


render_sidebar()


if not st.session_state.sql_session_id:

    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">
                Welcome to CareConnect AI
            </div>
            <div class="hero-subtitle">
                Start a conversation with your intelligent
                telehealth receptionist.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Start conversation",
        type="primary",
    ):

        try:
            create_session()
            st.rerun()

        except ApiError as error:
            handle_error(error)

    st.stop()


render_chat()


st.markdown(
    """
    <div class="app-footer">
        CareConnect AI | Powered by Microsoft Foundry,
        FastAPI, MCP and Azure SQL
    </div>
    """,
    unsafe_allow_html=True,
)