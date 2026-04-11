import sys
import streamlit as st
import os
import json
import time
from pathlib import Path

# Ensure project root is on sys.path so `app.*` imports work
# regardless of how/where Streamlit is invoked.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.state.db import StateDB
from app.state.models import CandidateStatus
from app.state.checkpoint import CheckpointManager
from app.ui.runner import BatchRunner
from app.composer.pdf_writer import generate_resume_pdf
from app.email_handler.sender import send_outreach_email, send_final_pdf_email


st.set_page_config(page_title="Dashboard - Resume Finetuner", page_icon="📄", layout="wide")

db_path = Path(os.getcwd()) / "resume_tuner.db"
db = StateDB(db_path)
config = db.get_config()

if not config:
    st.switch_page("pages/1_Setup.py")

if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "show_checkpoint_dialog" not in st.session_state:
    st.session_state.show_checkpoint_dialog = False
if "active_candidate_dialog" not in st.session_state:
    st.session_state.active_candidate_dialog = None


@st.cache_data(ttl=30)
def _load_candidates(db_path_str: str) -> list[dict]:
    """Cached DB query - returns all candidates as plain dicts, newest first."""
    _db = StateDB(Path(db_path_str))
    with _db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM candidates ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]


def _do_send_email(cand_id: int, status: str, db: StateDB, config) -> None:
    """Dispatch to correct sender based on status and advance DB state.

    Raises RuntimeError if the candidate is not found or if the send fails,
    so callers can display st.error.
    """
    candidate = db.get_candidate(cand_id)
    if candidate is None:
        raise RuntimeError(f"Candidate {cand_id} not found in database.")
    if status == CandidateStatus.PAYMENT_CONFIRMED.value:
        ok = send_final_pdf_email(candidate, config)
        if not ok:
            raise RuntimeError("Email send failed - check SMTP config.")
        db.set_status(cand_id, CandidateStatus.OUTPUT_SENT)
        db.update_candidate(cand_id, {"output_sent_at": time.strftime('%Y-%m-%d %H:%M:%S')})
    else:
        ok = send_outreach_email(candidate, config)
        if not ok:
            raise RuntimeError("Email send failed - check SMTP config.")
        db.set_status(cand_id, CandidateStatus.EMAIL_SENT)
        db.update_candidate(cand_id, {"email_sent_at": time.strftime('%Y-%m-%d %H:%M:%S')})


@st.dialog("Confirm Email Send")
def _email_dialog(cand_id: int, status: str, db_path_str: str) -> None:
    """Confirmation modal for Send Email checkbox. Opens a fresh DB connection
    to fetch the CandidateRecord required by sender functions."""
    _db     = StateDB(Path(db_path_str))
    _config = _db.get_config()
    _cand   = _db.get_candidate(cand_id)
    if _cand is None:
        st.error(f"Candidate {cand_id} not found in database.")
        return

    email_addr = _cand.candidate_email or "(no email on record)"
    st.write(f"Send email to **{email_addr}**?")

    # Show which template will be used - disabled (content determined by status in templates.py)
    if status in (CandidateStatus.HAPPY_PATH.value, CandidateStatus.MISSING_DETAILS.value):
        _default_tmpl = "Happy Path" if status == CandidateStatus.HAPPY_PATH.value else "Missing Details"
        st.selectbox(
            "Template",
            options=["Happy Path", "Missing Details"],
            index=0 if _default_tmpl == "Happy Path" else 1,
            disabled=True,
            help="Template is determined by candidate status. Editing requires changes outside app/ui/ scope.",
        )

    col_send, col_cancel = st.columns(2)
    if col_send.button("Send", key=f"dlg_send_{cand_id}"):
        try:
            _do_send_email(cand_id, status, _db, _config)
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(str(e))
    if col_cancel.button("Cancel", key=f"dlg_cancel_{cand_id}"):
        st.rerun()


# Send Email checkbox - eligible statuses only, never pre-checked
_EMAIL_ELIGIBLE = {
    CandidateStatus.HAPPY_PATH.value,
    CandidateStatus.MISSING_DETAILS.value,
    CandidateStatus.PAYMENT_CONFIRMED.value,
}

st.title("Recruiter Dashboard")

# Top controls
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader(f"Candidates from: {config.source_folder}")
with col2:
    if st.session_state.is_running:
        st.button("Processing Batch...", disabled=True)
        st.spinner("Processing resumes in background...")
    else:
        if st.button("Start New Batch", type="primary"):
            ckpt_manager = CheckpointManager(db)
            ckpt = ckpt_manager.get_resume_point(config.source_folder)
            if ckpt and ckpt.last_processed_filename:
                st.session_state.show_checkpoint_dialog = True
            else:
                st.session_state.is_running = True
                runner = BatchRunner(db_path, st.session_state)
                runner.start()
                st.rerun()

if st.session_state.show_checkpoint_dialog:
    st.warning("A previous checkpoint was found.")
    ckpt_manager = CheckpointManager(db)
    ckpt = ckpt_manager.get_resume_point(config.source_folder)
    st.write(f"Resume from {ckpt.last_processed_filename}? (Batch {ckpt.batch_number}, {ckpt.total_processed} processed so far)")
    
    col_y, col_n = st.columns(2)
    if col_y.button("Yes, Resume"):
        st.session_state.show_checkpoint_dialog = False
        st.session_state.is_running = True
        runner = BatchRunner(db_path, st.session_state)
        # Note: logic for skipping is technically handled by PENDING status.
        # Checkpoint is just for metrics logging in this simpler state-based model.
        runner.start()
        st.rerun()
    if col_n.button("No, Start Fresh"):
        st.session_state.show_checkpoint_dialog = False
        st.session_state.is_running = True
        # Could delete previous checkpoints here if needed
        runner = BatchRunner(db_path, st.session_state)
        runner.start()
        st.rerun()

st.divider()

# List candidates
candidates_raw = _load_candidates(str(db_path))

if not candidates_raw:
    st.info("No candidates found. Start a batch to discover resumes.")
else:
    _STATUS_OPTIONS = ["All"] + [s.value for s in CandidateStatus]
    status_filter = st.selectbox("Filter by Status", options=_STATUS_OPTIONS)

    # Table header
    _h1, _h2, _h3, _h4, _h5 = st.columns([3, 2, 2, 2, 3])
    _h1.markdown("**Candidate**")
    _h2.markdown("**Source File**")
    _h3.markdown("**Status**")
    _h4.markdown("**Email Sent At**")
    _h5.markdown("**Actions**")
    st.divider()

    for row in candidates_raw:
        cand_id = row["id"]
        status  = row["status"]

        if status_filter != "All" and status != status_filter:
            continue

        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 3])
        c1.write(row["candidate_name"] or row["source_filename"])
        c2.write(row["source_filename"])
        c3.write(status)
        c4.write(row["email_sent_at"] or "-")

        with c5:
            if status == CandidateStatus.MISSING_DETAILS.value:
                if st.button("Fill Missing Details", key=f"btn_fill_{cand_id}"):
                    st.session_state.active_candidate_dialog = cand_id

            elif status == CandidateStatus.AWAITING_PAYMENT.value:
                if st.button("Confirm Payment", key=f"btn_pay_{cand_id}"):
                    db.set_status(cand_id, CandidateStatus.PAYMENT_CONFIRMED)
                    st.cache_data.clear()
                    st.success("Payment confirmed!")
                    st.rerun()

            elif status == CandidateStatus.PAYMENT_CONFIRMED.value:
                if st.button("Send Resume", key=f"btn_send_{cand_id}"):
                    try:
                        _do_send_email(cand_id, status, db, config)
                        st.cache_data.clear()
                        st.success("Resume sent successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to send email: {e}")

            elif status == CandidateStatus.ERROR.value:
                err = (row.get("error_message") or "Unknown error")[:120]
                st.error(err)

            # Send Email checkbox - eligible statuses only, never pre-checked
            if status in _EMAIL_ELIGIBLE:
                if st.checkbox("Send Email", key=f"chk_email_{cand_id}", value=False):
                    # Reset checkbox in session_state before opening dialog
                    # to prevent re-open loop on subsequent reruns.
                    st.session_state[f"chk_email_{cand_id}"] = False
                    _email_dialog(cand_id, status, str(db_path))

        # Fill-missing-details form - shown inline below the row when active
        if st.session_state.active_candidate_dialog == cand_id:
            st.markdown("### Provide Missing Details")
            try:
                missing_fields = json.loads(row["missing_fields"])
            except Exception:
                missing_fields = []

            with st.form(key=f"form_{cand_id}"):
                inputs = {}
                for field in missing_fields:
                    inputs[field] = st.text_input(f"Provide value for: {field}")

                submit = st.form_submit_button("Save & Complete")
                if submit:
                    try:
                        llm_output = json.loads(row["llm_output_json"])
                        for k, v in inputs.items():
                            if k.lower() in ["phone", "email", "linkedin"]:
                                if "contact" not in llm_output:
                                    llm_output["contact"] = {}
                                llm_output["contact"][k.lower()] = v
                            else:
                                llm_output[k] = v

                        llm_output["missing_fields"] = []
                        file_dest = config.destination_folder
                        new_output_pdf = Path(file_dest) / f"{llm_output.get('candidate_name', 'Candidate')}_finetuned.pdf"

                        photo_bytes = None
                        if row["photo_path"] and Path(row["photo_path"]).exists():
                            photo_bytes = Path(row["photo_path"]).read_bytes()

                        generate_resume_pdf(llm_output, photo_bytes, new_output_pdf)

                        db.update_candidate(cand_id, {
                            "recruiter_additions": json.dumps(inputs),
                            "llm_output_json": json.dumps(llm_output),
                            "missing_fields": "[]",
                            "output_pdf_path": str(new_output_pdf)
                        })
                        db.set_status(cand_id, CandidateStatus.AWAITING_PAYMENT)

                        st.session_state.active_candidate_dialog = None
                        st.cache_data.clear()
                        st.success("Details updated and resume regenerated! Awaiting payment.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error regenerating resume: {e}")

        st.divider()

