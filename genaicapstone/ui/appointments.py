import streamlit as st


PREVIEW_KEY = "cancellation_preview"


def render_appointments(
    api_request,
    token,
    session_id,
    show_api_error,
):
    st.subheader("My upcoming appointments")

    st.caption(
        "Only upcoming confirmed appointments are listed. "
        "Cancellation requires a separate confirmation."
    )

    if PREVIEW_KEY not in st.session_state:
        st.session_state[PREVIEW_KEY] = None

    preview = st.session_state[PREVIEW_KEY]

    if preview and preview["session_id"] != session_id:
        st.session_state[PREVIEW_KEY] = None
        preview = None

    notice = st.session_state.pop(
        "appointment_notice",
        None,
    )

    if notice:
        st.success(notice)

    try:
        result = api_request(
            "GET",
            "/appointments/bookings",
            token=token,
        )
    except Exception as error:
        show_api_error(error)
        return

    appointments = result["appointments"]

    if appointments:
        rows = [
            {
                "Appointment ID": item["appointment_id"],
                "Doctor": item["display_name"],
                "Specialty": item["specialty_name"],
                "City": item["city"],
                "Starts": item["starts_at_local"],
                "Ends": item["ends_at_local"],
                "Status": item["status"],
            }
            for item in appointments
        ]

        st.dataframe(
            rows,
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("You have no upcoming confirmed appointments.")

    if preview:
        render_cancellation_confirmation(
            api_request=api_request,
            token=token,
            preview=preview,
            show_api_error=show_api_error,
        )
        return

    if not appointments:
        return

    by_id = {
        item["appointment_id"]: item
        for item in appointments
    }

    def appointment_label(appointment_id):
        item = by_id[appointment_id]

        return (
            f"Appointment {appointment_id} | "
            f"{item['display_name']} | "
            f"{item['starts_at_local']}"
        )

    selected_id = st.selectbox(
        "Select an appointment",
        options=list(by_id),
        format_func=appointment_label,
        key=f"appointment_selection_{session_id}",
    )

    st.warning(
        "Preparing this cancellation replaces any other "
        "unconfirmed action in this conversation session."
    )

    if st.button(
        "Review cancellation",
        key="prepare_cancellation_button",
    ):
        try:
            with st.spinner("Preparing cancellation..."):
                prepared = api_request(
                    "POST",
                    "/actions/cancellations/prepare",
                    token=token,
                    payload={
                        "session_id": session_id,
                        "appointment_id": selected_id,
                    },
                )

            st.session_state[PREVIEW_KEY] = {
                "session_id": session_id,
                "prepared": prepared,
            }

            st.rerun()

        except Exception as error:
            show_api_error(error)


def render_cancellation_confirmation(
    api_request,
    token,
    preview,
    show_api_error,
):
    prepared = preview["prepared"]

    st.divider()
    st.subheader("Review cancellation")

    st.write(
        {
            "Appointment ID": prepared["appointment_id"],
            "Doctor": prepared["doctor_name"],
            "Appointment starts (UTC)": (
                prepared["starts_at_utc"]
            ),
            "Confirmation expires (UTC)": (
                prepared["expires_at_utc"]
            ),
        }
    )

    st.warning(
        "Confirming will cancel this appointment. "
        "The backend will recheck ownership, expiry "
        "and the appointment version."
    )

    if st.button(
        "Confirm cancellation",
        type="primary",
        key="execute_cancellation_button",
    ):
        try:
            with st.spinner("Cancelling appointment..."):
                result = api_request(
                    "POST",
                    "/actions/cancellations/execute",
                    token=token,
                    payload={
                        "session_id": preview["session_id"],
                        "action_id": prepared["action_id"],
                        "confirmed": True,
                    },
                )

            st.session_state[PREVIEW_KEY] = None

            if result.get("already_processed"):
                message = (
                    "This cancellation was already completed. "
                    "No additional change was made."
                )
            else:
                message = (
                    f"Appointment {result['appointment_id']} "
                    "was cancelled successfully."
                )

            st.session_state.appointment_notice = message
            st.rerun()

        except Exception as error:
            show_api_error(error)

    if st.button(
        "Back without confirming",
        key="leave_cancellation_preview",
    ):
        st.session_state[PREVIEW_KEY] = None
        st.rerun()

    st.caption(
        "Back does not execute or reject the stored action. "
        "It remains unconfirmed until it expires or is "
        "superseded. This screen cannot execute it after "
        "you leave without preparing another review."
    )