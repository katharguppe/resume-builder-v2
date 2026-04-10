"""
PDF Composer Module

This module takes the LLM's structured JSON output and a photo (optional)
and generates a professionally formatted PDF resume.
"""

from .pdf_writer import generate_resume_pdf

__all__ = ["generate_resume_pdf"]
