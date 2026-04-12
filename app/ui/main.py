import sys
import streamlit as st
import os
from pathlib import Path

# Ensure project root is on sys.path so `app.*` imports work
# regardless of how/where Streamlit is invoked.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.state.db import StateDB

def main():
    st.set_page_config(page_title="Resume Finetuner", page_icon="📄", layout="wide")
    
    db_path = Path(os.getenv("DB_PATH", "resume_tuner.db"))
    db = StateDB(db_path)
    
    config_record = db.get_config()
    
    st.title("Loading...")
    
    # Simple router
    if not config_record:
        st.switch_page("pages/1_Setup.py")
    else:
        st.switch_page("pages/2_Dashboard.py")

if __name__ == "__main__":
    main()
