def build_extraction_prompt(resume_text: str) -> str:
    """
    Minimal prompt for Haiku to extract name, email, phone from a resume.
    """
    return f"""Extract the candidate's name, email address, and phone number from the resume below.

Respond ONLY with valid JSON — no markdown, no explanation:
{{"candidate_name": "string", "email": "string", "phone": "string"}}

Use empty string "" for any field not found in the resume.

=== RESUME ===
{resume_text}""".strip()


def build_finetuning_prompt(resume_text: str, jd_text: str, best_practice_text: str, candidate_name: str) -> str:
    """
    Builds the structured prompt for Claude Sonnet to fine-tune a candidate's resume against a JD.
    """
    prompt = f"""
You are an expert technical recruiter and resume writer. Your task is to fine-tune the candidate's resume to better align with the provided Job Description (JD).
You must strictly follow the provided best practice format.

CANDIDATE NAME: {candidate_name}

=== BEST PRACTICE FORMATTING TO FOLLOW ===
{best_practice_text}

=== JOB DESCRIPTION ===
{jd_text}

=== CANDIDATE ORIGINAL RESUME ===
{resume_text}

=== OBJECTIVE ===
Rewrite the candidate's resume to align tightly with the JD.

Rules for every bullet point:
1. Use the EXACT phrasing from the JD wherever possible — if the JD says
   "admissions management", write "admissions management", not "student
   intake coordination".
2. Within each role, put the bullet most directly relevant to the JD first.
3. Do not fabricate facts. Rephrase and reorder only — never invent experience,
   dates, companies, or qualifications not present in the source resume.

=== CRITICAL CONSTRAINT ===
Do not invent, fabricate, or add any experience, qualifications, dates, or companies that are not present in the source resume text. You may rephrase, reorder, and reformat — but you must not add facts.

If a piece of information (such as phone number, email, linkedin, etc) is not in the source resume, you must leave it blank in the relevant field and list it in the `missing_fields` output array.

=== OUTPUT SCHEMA ===
You must respond with ONLY valid JSON matching this schema exactly. No markdown blocks, no conversational text.
{{
  "candidate_name": "{candidate_name}",
  "contact": {{ "email": "string", "phone": "string", "linkedin": "string" }},
  "summary": "string — 3-4 lines, JD-aligned",
  "experience": [ {{ "title": "string", "company": "string", "dates": "string", "bullets": ["string"] }} ],
  "education": [ {{ "degree": "string", "institution": "string", "year": "string" }} ],
  "skills": ["string"],
  "missing_fields": ["string — any field that was blank or unclear in source resume"]
}}
"""
    return prompt.strip()
