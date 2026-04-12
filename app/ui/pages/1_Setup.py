import sys
import streamlit as st
import os
import json
try:
    import tkinter
    import tkinter.filedialog
    _TKINTER_AVAILABLE = True
except Exception:
    _TKINTER_AVAILABLE = False
from pathlib import Path
from dotenv import set_key, load_dotenv
from cryptography.fernet import Fernet

# Ensure project root is on sys.path so `app.*` imports work
# regardless of how/where Streamlit is invoked.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.state.db import StateDB, AuthDB
from app.email_handler.crypto import encrypt_password


db_path = Path(os.getenv("DB_PATH", "resume_tuner.db"))
db = StateDB(db_path)

st.set_page_config(page_title="Setup - Resume Finetuner", page_icon="⚙️", layout="wide")

_auth_db = st.session_state.setdefault("auth_db", AuthDB(Path(os.getenv("AUTH_DB_PATH", "resume_builder.db"))))
if not _auth_db.get_session(st.session_state.get("auth_token", "")):
    st.error("Please sign in to continue.")
    st.switch_page("pages/0_Login.py")
    st.stop()

st.title("System Setup")
st.markdown("Configure the system before processing candidates.")

# ── Load saved config for pre-population ─────────────────────────────────────
saved = db.get_config()

# ── Session-state keys for folder paths (browser-side after picker) ───────────
if "sf_source"  not in st.session_state:
    st.session_state.sf_source = saved.source_folder if saved else ""
if "sf_dest"    not in st.session_state:
    st.session_state.sf_dest   = saved.destination_folder if saved else ""

# ── Helper: open native Windows folder picker ────────────────────────────────
def _pick_folder(initial: str = "") -> str:
    """Open a native folder picker and return the selected path (or '' if cancelled)."""
    root = tkinter.Tk()
    root.withdraw()       # hide the root window
    root.wm_attributes("-topmost", True)   # bring dialog to front
    folder = tkinter.filedialog.askdirectory(
        initialdir=initial or os.path.expanduser("~"),
        title="Select Folder"
    )
    root.destroy()
    return folder  # empty string if cancelled


# ── Banner when editing a saved config ───────────────────────────────────────
if saved:
    col_banner, col_clear = st.columns([6, 1])
    with col_banner:
        st.success("✅ A saved configuration was found and pre-loaded below. Edit any field and click **Save Configuration** to update.")
    with col_clear:
        if st.button("🗑 Clear / New Job"):
            st.session_state.sf_source = ""
            st.session_state.sf_dest   = ""
            saved = None
            st.rerun()

st.divider()

# ── Directory Configuration ───────────────────────────────────────────────────
st.subheader("📁 Directory Configuration")

# Source Folder row
src_col, src_btn = st.columns([5, 1])
with src_col:
    source_folder = st.text_input(
        "Source Folder Path (containing JD file and a resumes subfolder)",
        value=st.session_state.sf_source,
        key="txt_source"
    )
with src_btn:
    st.write("")  # vertical alignment spacer
    if _TKINTER_AVAILABLE and st.button("Browse…", key="btn_src"):
        picked = _pick_folder(st.session_state.sf_source)
        if picked:
            st.session_state.sf_source = picked
            st.rerun()

# Destination Folder row
dst_col, dst_btn = st.columns([5, 1])
with dst_col:
    destination_folder = st.text_input(
        "Destination Folder Path (where fine-tuned PDFs will be written)",
        value=st.session_state.sf_dest,
        key="txt_dest"
    )
with dst_btn:
    st.write("")
    if _TKINTER_AVAILABLE and st.button("Browse…", key="btn_dst"):
        picked = _pick_folder(st.session_state.sf_dest)
        if picked:
            st.session_state.sf_dest = picked
            st.rerun()

# Sync text-input back to session state (in case user typed directly)
st.session_state.sf_source = source_folder
st.session_state.sf_dest   = destination_folder

bp_default = ""
if saved and saved.best_practice_paths:
    try:
        bp_default = "\n".join(json.loads(saved.best_practice_paths))
    except Exception:
        bp_default = ""

bp_paths = st.text_area(
    "Best Practice Resume Paths (Optional - one path per line)",
    value=bp_default
)

st.divider()

# ── Recruiter Information ─────────────────────────────────────────────────────
st.subheader("👤 Recruiter Information")
recruiter_name  = st.text_input("Recruiter Name",  value=saved.recruiter_name  if saved else "")
recruiter_email = st.text_input("Recruiter Email", value=saved.recruiter_email if saved else "")

st.divider()

# ── SMTP Configuration ────────────────────────────────────────────────────────
st.subheader("✉️ SMTP Configuration (For Outreach Emails)")
smtp_server   = st.text_input("SMTP Server", value=saved.smtp_server if saved else "smtp.gmail.com")
smtp_port     = st.number_input("SMTP Port", value=int(saved.smtp_port) if saved else 587, step=1)
smtp_password = st.text_input(
    "SMTP App Password (leave blank to keep existing)",
    type="password",
    help="Only enter a new password if you want to change it. Leave blank to keep the saved one."
)

st.divider()

# ── Business Settings ─────────────────────────────────────────────────────────
st.subheader("💼 Business Settings")
service_fee     = st.text_input("Service Fee Amount (₹)", value=saved.service_fee if saved else "499")
_BATCH_OPTIONS = [5, 10, 20, 50, "All"]
_saved_bs = str(saved.batch_size) if (saved and saved.batch_size and saved.batch_size > 0) else "All"
_opts_str = [str(x) for x in _BATCH_OPTIONS]
batch_size_choice = st.selectbox(
    "Batch Size",
    options=_BATCH_OPTIONS,
    index=_opts_str.index(_saved_bs) if _saved_bs in _opts_str else len(_BATCH_OPTIONS) - 1,
)

# Anthropic API key
gemini_api_key = st.text_input(
    "Anthropic API Key (leave blank to keep existing)",
    type="password",
    help="Only enter if you want to change the key. Leave blank to keep the one in .env."
)

st.divider()

# ── Save button ───────────────────────────────────────────────────────────────
if st.button("💾 Save Configuration", type="primary"):
    errors = []
    if not source_folder or not os.path.exists(source_folder):
        errors.append("Invalid or missing Source Folder path.")
    if not destination_folder or not os.path.exists(destination_folder):
        errors.append("Invalid or missing Destination Folder path.")
    if not recruiter_name or not recruiter_email:
        errors.append("Recruiter Name and Email are required.")
    if not smtp_server:
        errors.append("SMTP Server is required.")
    # Password required only on first-time setup
    if not saved and not smtp_password:
        errors.append("SMTP App Password is required for first-time setup.")
    if not saved and not gemini_api_key:
        errors.append("Anthropic API Key is required for first-time setup.")

    batch_size = 0 if batch_size_choice == "All" else int(batch_size_choice)

    if errors:
        for err in errors:
            st.error(err)
    else:
        with st.spinner("Saving configuration…"):
            env_path = Path(os.getcwd()) / ".env"

            # Encryption key - generate once
            load_dotenv(dotenv_path=env_path)
            enc_key_str = os.getenv("ENCRYPTION_KEY")
            if not enc_key_str:
                enc_key = Fernet.generate_key()
                enc_key_str = enc_key.decode("utf-8")
                set_key(str(env_path), "ENCRYPTION_KEY", enc_key_str)

            # Encrypt password only if a new one was provided
            if smtp_password:
                encrypted_pwd = encrypt_password(smtp_password, enc_key_str)
            else:
                encrypted_pwd = saved.smtp_password if saved else ""

            # Best practice paths
            bp_list = [p.strip() for p in bp_paths.split("\n") if p.strip()]
            bp_json = json.dumps(bp_list)

            config_data = {
                "source_folder":      source_folder,
                "recruiter_name":     recruiter_name,
                "recruiter_email":    recruiter_email,
                "smtp_server":        smtp_server,
                "smtp_port":          int(smtp_port),
                "smtp_password":      encrypted_pwd,
                "service_fee":        service_fee,
                "batch_size":         batch_size,
                "destination_folder": destination_folder,
                "best_practice_paths": bp_json,
            }

            db.save_config(config_data)

            # Save Anthropic key only if entered
            if gemini_api_key:
                set_key(str(env_path), "ANTHROPIC_API_KEY", gemini_api_key)

        st.success("✅ Configuration saved successfully!")
        st.switch_page("pages/2_Dashboard.py")
