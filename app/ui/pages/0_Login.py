import os
from pathlib import Path

import streamlit as st

from app.state.db import AuthDB
from app.auth.otp import issue_otp, send_otp_email, verify_otp
from app.auth.session import create_session

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))


def _get_auth_db() -> AuthDB:
    if "auth_db" not in st.session_state:
        st.session_state["auth_db"] = AuthDB(DB_PATH)
    return st.session_state["auth_db"]


def _is_logged_in() -> bool:
    token = st.session_state.get("auth_token")
    if not token:
        return False
    db = _get_auth_db()
    session = db.get_session(token)
    return session is not None


def render_email_step():
    st.subheader("Sign In")
    email = st.text_input("Email address", key="login_email")
    if st.button("Send Code"):
        if not email or "@" not in email:
            st.error("Enter a valid email address.")
            return
        db = _get_auth_db()
        otp_code = issue_otp(db, email)
        sent = send_otp_email(email, otp_code)
        if sent:
            st.session_state["otp_email"] = email
            st.session_state["otp_step"] = True
            st.success(f"Code sent to {email}. Check your inbox.")
            st.rerun()
        else:
            st.error("Failed to send code. Check SMTP configuration.")


def render_otp_step():
    email = st.session_state.get("otp_email", "")
    st.subheader("Enter Your Code")
    st.caption(f"Code sent to: {email}")
    code = st.text_input("6-digit code", max_chars=6, key="otp_code_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Verify"):
            if not code or not code.isdigit() or len(code) != 6:
                st.error("Enter the 6-digit code from your email.")
                return
            db = _get_auth_db()
            if verify_otp(db, email, code):
                token = create_session(db, email)
                st.session_state["auth_token"] = token
                st.session_state["auth_email"] = email
                st.session_state.pop("otp_step", None)
                st.session_state.pop("otp_email", None)
                st.success("Signed in successfully!")
                st.rerun()
            else:
                st.error("Invalid or expired code. Request a new one.")
    with col2:
        if st.button("Use a different email"):
            st.session_state.pop("otp_step", None)
            st.session_state.pop("otp_email", None)
            st.rerun()


def main():
    st.set_page_config(page_title="JobOS - Sign In", page_icon="🔐")
    st.title("JobOS Resume Builder")

    if _is_logged_in():
        email = st.session_state.get("auth_email", "")
        st.success(f"Signed in as {email}")
        if st.button("Sign Out"):
            db = _get_auth_db()
            token = st.session_state.get("auth_token")
            if token:
                db.expire_session(token)
            for key in ("auth_token", "auth_email", "otp_step", "otp_email"):
                st.session_state.pop(key, None)
            st.rerun()
        return

    if st.session_state.get("otp_step"):
        render_otp_step()
    else:
        render_email_step()


main()
