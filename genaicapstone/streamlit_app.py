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

EXECUTION_ENDPOINTS = {
    "BOOK": "/actions/bookings/execute",
    "CANCEL": "/actions/cancellations/execute",
    "RESCHEDULE": "/actions/reschedules/execute",
}

WORKFLOW_LABELS = {
    "BOOK": "Book appointment",
    "CANCEL": "Cancel appointment",
    "RESCHEDULE": "Reschedule appointment",
}


st.set_page_config(
    page_title="CareConnect AI",
    page_icon="✚",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
    }

    [data-testid="stSidebar"] {
        background: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }

    [data-testid="stSidebar"] * {
        color: #172B4D;
    }

    [data-testid="stChatMessage"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 12px;
    }

    [data-testid="stChatInput"] {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 12px !important;
    }

    [data-testid="stChatInput"] textarea {
        background: #FFFFFF !important;
        color: #172B4D !important;
        -webkit-text-fill-color: #172B4D !important;
        caret-color: #087F8C !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #718096 !important;
        -webkit-text-fill-color: #718096 !important;
    }

    div[data-baseweb="input"] input {
        background: #FFFFFF !important;
        color: #172B4D !important;
        -webkit-text-fill-color: #172B4D !important;
    }

    .hero {
        background: linear-gradient(
            115deg,
            #0D6474,
            #138B96
        );
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 24px;
    }

    .hero h1 {
        color: #FFFFFF;
        margin-bottom: 8px;
    }

    .hero p {
        color: #E5F7F8;
        margin-bottom: 0;
    }

    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }

    div.stButton > button[kind="primary"] {
        background: #087F8C;
        color: #FFFFFF;
        border: none;
    }

    .workflow-heading {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #64748B;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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
            timeout=httpx.Timeout(180.0, connect=10.0),
            follow_redirects=False,
        ) as client:
            response = client.request(
                method,
                f"{API_URL}{path}",
                headers=headers,
                json=payload,
            )

    except httpx.TimeoutException as error:
        raise ApiError(
            "Request timed out. The result may be uncertain. "
            "Do not automatically retry a state-changing operation."
        ) from error

    except httpx.RequestError as error:
        raise ApiError(
            "Unable to connect to FastAPI."
        ) from error

    if not response.is_success:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None

        if not isinstance(detail, str):
            detail = f"HTTP {response.status_code}"

        raise ApiError(detail, response.status_code)

    try:
        return response.json()
    except ValueError as error:
        raise ApiError(
            "Unexpected response from FastAPI."
        ) from error


def initialize_state():
    defaults = {
        "token": None,
        "customer": None,
        "session_id": None,
        "messages": [],
        "pending_action": None,
        "workflow": None,
        "chat_blocked": False,
        "execution_uncertain": False,
        "safety_paused": False,
        "notice": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_login():
    st.session_state.token = None
    st.session_state.customer = None
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.pending_action = None
    st.session_state.workflow = None
    st.session_state.chat_blocked = False
    st.session_state.execution_uncertain = False
    st.session_state.safety_paused = False


def handle_error(error):
    if error.status_code == 401:
        clear_login()
        st.session_state.notice = (
            "Your login has expired. Please sign in again."
        )
        st.rerun()

    st.error(str(error))


def create_session():
    result = api_request(
        "POST",
        "/sessions",
        token=st.session_state.token,
    )

    st.session_state.session_id = result["session_id"]
    st.session_state.messages = []
    st.session_state.pending_action = None
    st.session_state.workflow = None
    st.session_state.chat_blocked = False
    st.session_state.execution_uncertain = False
    st.session_state.safety_paused = False


def select_workflow(workflow):
    result = api_request(
        "POST",
        "/workflow/select",
        token=st.session_state.token,
        payload={
            "session_id": st.session_state.session_id,
            "workflow": workflow,
        },
    )

    st.session_state.workflow = result["current_workflow"]


def refresh_pending_action():
    result = api_request(
        "GET",
        f"/actions/pending/{st.session_state.session_id}",
        token=st.session_state.token,
    )

    st.session_state.pending_action = result.get("action")


def format_time(value):
    if not value:
        return "Not available"

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            return "Not available"

        return parsed.astimezone(IST).strftime(
            "%d %B %Y, %I:%M %p IST"
        )

    except ValueError:
        return "Not available"


def render_login():
    st.markdown(
        """
        <div class="hero">
            <h1>CareConnect AI</h1>
            <p>Your intelligent healthcare receptionist.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.5, 1])

    with center:
        st.subheader("Welcome back")
        st.caption("Sign in with your registered account.")

        if st.session_state.notice:
            st.info(st.session_state.notice)
            st.session_state.notice = None

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Sign in",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not username.strip() or not password:
                st.error("Enter your username and password.")
                return

            try:
                with st.spinner("Signing in..."):
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


def render_sidebar():
    customer = st.session_state.customer

    with st.sidebar:
        st.title("CareConnect AI")
        st.caption("AI-powered appointment assistant")

        st.divider()

        st.write(f"**{customer['username']}**")
        st.caption(customer["customer_code"])

        st.divider()

        if st.session_state.session_id:
            st.markdown(
                '<div class="workflow-heading">'
                'APPOINTMENT ACTIONS'
                '</div>',
                unsafe_allow_html=True,
            )

            disabled = (
                st.session_state.pending_action is not None
                or st.session_state.execution_uncertain
                or st.session_state.chat_blocked
                or st.session_state.safety_paused
            )

            for workflow, label in WORKFLOW_LABELS.items():
                selected = (
                    st.session_state.workflow == workflow
                )

                button_label = (
                    f"{label} — Selected"
                    if selected
                    else label
                )

                if st.button(
                    button_label,
                    key=f"workflow_{workflow}",
                    use_container_width=True,
                    type="primary" if selected else "secondary",
                    disabled=disabled,
                ):
                    try:
                        select_workflow(workflow)
                        st.rerun()

                    except ApiError as error:
                        handle_error(error)

            if st.session_state.workflow:
                st.caption(
                    "Current workflow: "
                    + st.session_state.workflow
                )

            st.divider()

        if st.button(
            "New conversation",
            use_container_width=True,
        ):
            try:
                create_session()
                st.rerun()

            except ApiError as error:
                handle_error(error)

        if st.button(
            "Sign out",
            use_container_width=True,
        ):
            if st.session_state.session_id:
                try:
                    api_request(
                        "POST",
                        (
                            f"/sessions/"
                            f"{st.session_state.session_id}/close"
                        ),
                        token=st.session_state.token,
                    )
                except ApiError:
                    pass

            clear_login()
            st.rerun()

        st.divider()
        st.caption(
            "Synthetic-data capstone. "
            "Not intended for real patient care."
        )


def execute_pending_action(action):
    if st.session_state.safety_paused:
        st.error(
            "Appointment actions are paused after "
            "a potential emergency message."
        )
        return

    action_type = action["action_type"]
    endpoint = EXECUTION_ENDPOINTS.get(action_type)

    if endpoint is None:
        st.error("Unsupported action type.")
        return

    try:
        with st.spinner("Processing appointment..."):
            result = api_request(
                "POST",
                endpoint,
                token=st.session_state.token,
                payload={
                    "session_id": st.session_state.session_id,
                    "action_id": action["action_id"],
                    "confirmed": True,
                },
            )

        appointment_id = result["appointment_id"]

        st.session_state.pending_action = None
        st.session_state.execution_uncertain = False
        st.session_state.workflow = None

        verbs = {
            "BOOK": "booked",
            "CANCEL": "cancelled",
            "RESCHEDULE": "rescheduled",
        }

        if result.get("already_processed"):
            reply = (
                f"Appointment {appointment_id} "
                "was already processed. "
                "No duplicate change was made."
            )
        else:
            reply = (
                f"Appointment {appointment_id} "
                f"successfully {verbs[action_type]}."
            )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": reply,
                "tool_calls": [],
                "safety_status": "NORMAL",
            }
        )

        st.session_state.notice = reply
        st.rerun()

    except ApiError as error:
        if (
            error.status_code is None
            or error.status_code >= 500
        ):
            st.session_state.execution_uncertain = True

        handle_error(error)


def render_confirmation(action):
    action_type = action.get("action_type")

    if action_type not in EXECUTION_ENDPOINTS:
        st.error("Unsupported pending action.")
        return

    st.divider()
    st.subheader(
        f"Review {action_type.lower()} request"
    )

    st.info(
        "This operation has not been executed yet."
    )

    st.write(
        "**Doctor:**",
        action.get("display_name") or "Not available",
    )

    st.write(
        "**Specialty:**",
        action.get("specialty_name") or "Not available",
    )

    st.write(
        "**City:**",
        action.get("city") or "Not available",
    )

    if action_type == "BOOK":
        st.write(
            "**Proposed appointment:**",
            format_time(
                action.get("target_starts_at_local")
            ),
        )

    elif action_type == "CANCEL":
        st.write(
            "**Appointment ID:**",
            action.get("appointment_id"),
        )

        st.write(
            "**Current appointment:**",
            format_time(
                action.get("current_starts_at_local")
            ),
        )

    elif action_type == "RESCHEDULE":
        st.write(
            "**Appointment ID:**",
            action.get("appointment_id"),
        )

        st.write(
            "**Current appointment:**",
            format_time(
                action.get("current_starts_at_local")
            ),
        )

        st.write(
            "**Proposed appointment:**",
            format_time(
                action.get("target_starts_at_local")
            ),
        )

    st.caption(
        "Action expires: "
        + format_time(action.get("expires_at_utc"))
    )

    if (
        st.session_state.execution_uncertain
        or st.session_state.safety_paused
    ):
        st.error(
            "Confirmation is unavailable while "
            "the conversation is paused."
        )
        return

    required = {
        "BOOK": ["target_starts_at_local"],
        "CANCEL": [
            "appointment_id",
            "current_starts_at_local",
        ],
        "RESCHEDULE": [
            "appointment_id",
            "current_starts_at_local",
            "target_starts_at_local",
        ],
    }

    if any(
        not action.get(field)
        for field in required[action_type]
    ):
        st.error(
            "Required appointment details are missing. "
            "Confirmation is disabled."
        )
        return

    expires_at = action.get("expires_at_utc")

    try:
        expiry = datetime.fromisoformat(expires_at)
        now = datetime.now(expiry.tzinfo)

        if now >= expiry:
            st.error(
                "This action has expired. "
                "Start a new conversation and prepare it again."
            )
            return

    except (TypeError, ValueError, AttributeError):
        st.error(
            "Action expiry could not be verified."
        )
        return

    if st.button(
        f"Confirm {action_type.lower()}",
        type="primary",
        use_container_width=True,
        key="confirm_pending_action",
    ):
        execute_pending_action(action)


def process_message(message):
    st.session_state.messages.append(
        {
            "role": "user",
            "content": message,
            "tool_calls": [],
            "safety_status": "NORMAL",
        }
    )

    try:
        with st.spinner("Assistant is responding..."):
            response = api_request(
                "POST",
                "/chat",
                token=st.session_state.token,
                payload={
                    "session_id": st.session_state.session_id,
                    "message": message,
                },
            )

        safety_status = response.get(
            "safety_status",
            "NORMAL",
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response["reply"],
                "tool_calls": response.get(
                    "tool_calls",
                    [],
                ),
                "safety_status": safety_status,
            }
        )

        if safety_status == "POTENTIAL_EMERGENCY":
            st.session_state.safety_paused = True
            st.session_state.pending_action = None
            st.session_state.workflow = None
            st.rerun()

        refresh_pending_action()
        st.rerun()

    except ApiError as error:
        st.session_state.chat_blocked = True
        handle_error(error)


def render_chat():
    st.markdown(
        """
        <div class="hero">
            <h1>Your AI Healthcare Receptionist</h1>
            <p>
                Search, book, cancel and reschedule
                appointments through natural conversation.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.notice:
        st.success(st.session_state.notice)
        st.session_state.notice = None

    if not st.session_state.messages:
        st.info(
            "Choose Book, Cancel or Reschedule "
            "from the sidebar, then start chatting."
        )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if (
                message.get("safety_status")
                == "POTENTIAL_EMERGENCY"
            ):
                st.error(
                    "Potential medical emergency detected"
                )

            st.markdown(message["content"])

            if message.get("tool_calls"):
                with st.expander("Tool activity"):
                    st.json(message["tool_calls"])

    if st.session_state.safety_paused:
        st.error(
            "Normal appointment operations are paused "
            "following a potential emergency message. "
            "Seek appropriate emergency assistance. "
            "A new conversation can be started when appropriate."
        )

    elif st.session_state.pending_action:
        render_confirmation(
            st.session_state.pending_action
        )

    if st.session_state.chat_blocked:
        st.warning(
            "Conversation paused after an error. "
            "Check backend logs before continuing."
        )

    prompt = st.chat_input(
        "Ask your healthcare assistant...",
        max_chars=4000,
        disabled=(
            st.session_state.chat_blocked
            or st.session_state.execution_uncertain
            or st.session_state.safety_paused
            or st.session_state.pending_action is not None
        ),
    )

    if prompt and prompt.strip():
        process_message(prompt.strip())


initialize_state()

if not st.session_state.token:
    render_login()
    st.stop()

render_sidebar()

if not st.session_state.session_id:
    st.markdown(
        """
        <div class="hero">
            <h1>Welcome to CareConnect AI</h1>
            <p>
                Start a conversation with your intelligent
                telehealth receptionist.
            </p>
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