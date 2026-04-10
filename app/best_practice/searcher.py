import logging
from duckduckgo_search import DDGS

from app.config import config

logger = logging.getLogger(__name__)

GENERIC_BEST_PRACTICE_TEMPLATE = """
[BEST PRACTICE RESUME STRUCTURE]

1. Contact Information
- Full Name
- Phone, Email, LinkedIn (Optional: GitHub/Portfolio)

2. Professional Summary
- A concise 3-4 sentence paragraph highlighting key qualifications, years of experience, and alignment with the target role.

3. Professional Experience (Reverse Chronological)
- [Job Title] | [Company Name] | [Month, Year - Month, Year]
  - Use bullet points focused on achievements, not just responsibilities.
  - Start with action verbs.
  - Quantify results (e.g., "Increased sales by 15%", "Managed a team of 10").

4. Education
- [Degree] | [University Name] | [Graduation Year]

5. Skills
- Hard skills and tools relevant to the Job Description. Group them if possible (e.g., Languages, Frameworks, Tools).
"""

def search_best_practice(jd_title: str) -> str:
    """
    Search the web for best-practice resume templates tailored to the given job title.
    Returns the compiled text snippets from the top search results.
    If the search fails or yields no usable results, gracefully falls back to a generic template.
    
    Args:
        jd_title (str): The target job title to search (e.g., "Software Engineer").
        
    Returns:
        str: The combined best practice snippets or fallback template.
    """
    if not jd_title or not jd_title.strip():
        logger.warning("Empty jd_title provided to search_best_practice. Returning generic template.")
        return GENERIC_BEST_PRACTICE_TEMPLATE
        
    query = f"best practice resume template for {jd_title}"
    logger.info(f"Searching web for best practice templates: '{query}'")
    
    results_text = []
    try:
        ddgs = DDGS()
        # Fetch top 5 results
        results = ddgs.text(query, max_results=3)
        
        for res in results:
            title = res.get('title', '')
            body = res.get('body', '')
            if title or body:
                snippet = f"Source Idea: {title}\n{body}"
                results_text.append(snippet)
                
    except Exception as e:
        logger.warning(f"Web search for best practice templates failed: {e}. Falling back to standard template.")
        return GENERIC_BEST_PRACTICE_TEMPLATE
        
    if not results_text:
        logger.warning("No search results found for best practice template. Falling back to standard template.")
        return GENERIC_BEST_PRACTICE_TEMPLATE
        
    combined_text = "Found specialized industry advice:\n\n" + "\n\n---\n\n".join(results_text)
    combined_text += "\n\n--- Standard Fallback Structure ---\n" + GENERIC_BEST_PRACTICE_TEMPLATE
    
    # Approximate token truncation (1 token ~ 4 chars)
    max_chars = config.BEST_PRACTICE_MAX_TOKENS * 4
    if len(combined_text) > max_chars:
        logger.info(f"Truncating search results to approx {config.BEST_PRACTICE_MAX_TOKENS} tokens limits.")
        combined_text = combined_text[:max_chars] + "\n...(truncated)"
        
    return combined_text
