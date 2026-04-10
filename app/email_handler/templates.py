import json
import logging
from typing import List, Dict, Any
from app.state.models import CandidateRecord, ConfigRecord, CandidateStatus

logger = logging.getLogger(__name__)

def _parse_json_field(field_str: str, default: Any) -> Any:
    if not field_str:
        return default
    try:
        return json.loads(field_str)
    except Exception as e:
        logger.warning(f"Failed to parse JSON field: {e}")
        return default

def get_outreach_subject(candidate: CandidateRecord) -> str:
    jd_title = candidate.jd_title or "this role"
    return f"Your resume could be stronger for {jd_title} — here's how"

def get_final_subject(candidate: CandidateRecord) -> str:
    jd_title = candidate.jd_title or "this role"
    return f"Here is your fine-tuned resume for {jd_title}"

def _build_preview_html(candidate: CandidateRecord) -> str:
    llm_data = _parse_json_field(candidate.llm_output_json, {})
    
    summary = llm_data.get("summary", "No summary available.")
    experience_list = llm_data.get("experience", [])
    
    html = f"""
    <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #0056b3; margin: 20px 0;">
        <h3 style="margin-top: 0; color: #333;">Preview of Fine-tuned Resume</h3>
        <p><strong>Summary:</strong><br/>{summary}</p>
        <h4 style="margin-bottom: 5px; color: #333;">Experience Highlight:</h4>
        <ul style="margin-top: 5px;">
    """
    
    for exp in experience_list[:2]:
        title = exp.get("title", "")
        company = exp.get("company", "")
        html += f"<li><strong>{title}</strong> at {company}</li>"
        
    html += """
        </ul>
        <p style="color: #666; font-size: 0.9em; font-style: italic;">... plus full formatting, education, and skills sections.</p>
    </div>
    """
    return html

def _build_preview_text(candidate: CandidateRecord) -> str:
    llm_data = _parse_json_field(candidate.llm_output_json, {})
    summary = llm_data.get("summary", "No summary available.")
    experience_list = llm_data.get("experience", [])
    
    text = f"\n--- Preview of Fine-tuned Resume ---\nSummary:\n{summary}\n\nExperience Highlight:\n"
    for exp in experience_list[:2]:
        title = exp.get("title", "")
        company = exp.get("company", "")
        text += f"- {title} at {company}\n"
        
    text += "... plus full formatting, education, and skills sections.\n--------------------------------------\n\n"
    return text

def _build_missing_fields_section_html(candidate: CandidateRecord) -> str:
    if candidate.status != CandidateStatus.MISSING_DETAILS.value:
        return ""
        
    missing = _parse_json_field(candidate.missing_fields, [])
    if not missing:
        return ""
        
    html = """
    <div style="margin: 20px 0;">
        <p><strong>To complete your resume, I need a few more details:</strong></p>
        <ul>
    """
    for field in missing:
        html += f"<li>{field}</li>"
    html += """
        </ul>
        <p>Please reply with these details along with your payment screenshot.</p>
    </div>
    """
    return html

def _build_missing_fields_section_text(candidate: CandidateRecord) -> str:
    if candidate.status != CandidateStatus.MISSING_DETAILS.value:
        return ""
        
    missing = _parse_json_field(candidate.missing_fields, [])
    if not missing:
        return ""
        
    text = "\nTo complete your resume, I need a few more details:\n"
    for field in missing:
        text += f"- {field}\n"
    text += "\nPlease reply with these details along with your payment screenshot.\n\n"
    return text

def get_outreach_html(candidate: CandidateRecord, config: ConfigRecord) -> str:
    c_name = candidate.candidate_name or "Candidate"
    r_name = config.recruiter_name or "Recruiter"
    amt = config.service_fee or "499"
    
    preview_html = _build_preview_html(candidate)
    missing_html = _build_missing_fields_section_html(candidate)
    
    reply_instructions = "Simply reply with 'Yes' and attach your payment screenshot."
    if candidate.status == CandidateStatus.MISSING_DETAILS.value:
        reply_instructions = "" # The missing details section already includes the instruction
        
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <p>Hi {c_name},</p>
        <p>I'm {r_name}. I noticed your resume could be better presented for this role.</p>
        <p>We have a tool that re-formats and fine-tunes your resume specifically for the job description to improve your chances. Here is a sneak peek of what it looks like:</p>
        
        {preview_html}
        
        {missing_html}
        
        <p>For ₹{amt}, I can send you the complete fine-tuned PDF.</p>
        <p>{reply_instructions}</p>
        
        <p>Best regards,<br/>{r_name}</p>
    </body>
    </html>
    """
    return html

def get_outreach_text(candidate: CandidateRecord, config: ConfigRecord) -> str:
    c_name = candidate.candidate_name or "Candidate"
    r_name = config.recruiter_name or "Recruiter"
    amt = config.service_fee or "499"
    
    preview_text = _build_preview_text(candidate)
    missing_text = _build_missing_fields_section_text(candidate)
    
    reply_instructions = "Simply reply with 'Yes' and attach your payment screenshot."
    if candidate.status == CandidateStatus.MISSING_DETAILS.value:
        reply_instructions = ""
        
    text = f"""Hi {c_name},

I'm {r_name}. I noticed your resume could be better presented for this role.
We have a tool that re-formats and fine-tunes your resume specifically for the job description to improve your chances. Here is a sneak peek of what it looks like:
{preview_text}
{missing_text}
For ₹{amt}, I can send you the complete fine-tuned PDF.
{reply_instructions}

Best regards,
{r_name}
"""
    return text

def get_final_html(candidate: CandidateRecord, config: ConfigRecord) -> str:
    c_name = candidate.candidate_name or "Candidate"
    r_name = config.recruiter_name or "Recruiter"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <p>Hi {c_name},</p>
        <p>Thank you for confirming your payment and details.</p>
        <p>Please find attached your complete, fine-tuned resume PDF. We hope this helps you stand out for the role!</p>
        <p>Best regards,<br/>{r_name}</p>
    </body>
    </html>
    """
    return html

def get_final_text(candidate: CandidateRecord, config: ConfigRecord) -> str:
    c_name = candidate.candidate_name or "Candidate"
    r_name = config.recruiter_name or "Recruiter"
    
    text = f"""Hi {c_name},

Thank you for confirming your payment and details.
Please find attached your complete, fine-tuned resume PDF. We hope this helps you stand out for the role!

Best regards,
{r_name}
"""
    return text
