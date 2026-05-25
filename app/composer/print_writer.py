"""
Print Resume PDF Composer — JobOS Ideal Resume Structure (9 sections).

Separate from pdf_writer.py (ATS resume). ATS pipeline is NOT touched.
Entry point: generate_print_pdf(json_data, photo_bytes, output_path) -> bool
"""
import io
import logging
import pathlib
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
from reportlab.lib.utils import ImageReader

from .photo_handler import process_photo_for_pdf
from .pdf_writer import highlight_missing

logger = logging.getLogger(__name__)

_CURRENT_YEAR = datetime.now().year


def _extract_start_year(dates_str: str) -> int | None:
    """Extract first 4-digit year from a dates string like 'Jan 2019 - Dec 2022'."""
    if not dates_str:
        return None
    m = re.search(r'\b(19|20)\d{2}\b', dates_str)
    return int(m.group()) if m else None


def _apply_recency_rule(experience: list) -> list:
    """
    Return a copy of experience list with bullets trimmed by recency:
      - Index 0, 1 (latest two roles): all bullets kept
      - Index 2+: max 3 bullets
      - Any role whose start year < (_CURRENT_YEAR - 10): max 1 bullet

    Does NOT mutate the input list or its dicts.
    """
    result = []
    for i, exp in enumerate(experience):
        exp_copy = dict(exp)
        bullets = list(exp_copy.get("bullets", []))
        start_year = _extract_start_year(exp_copy.get("dates", ""))
        is_old = start_year is not None and start_year < (_CURRENT_YEAR - 13)

        if is_old:
            bullets = bullets[:1]
        elif i >= 2:
            bullets = bullets[:3]
        # i == 0 or 1: keep all bullets

        exp_copy["bullets"] = bullets
        result.append(exp_copy)
    return result


def generate_print_pdf(
    json_data: dict,
    photo_bytes: bytes | None,
    output_path: pathlib.Path,
) -> bool:
    """
    Generate a Print-format resume PDF following the JobOS 9-section structure.

    Sections:
      1 Personal Details   2 Profile Links        3 Professional Summary
      4 Skills             5 Professional Experience  6 Education
      7 Languages          8 Certifications (cond)    9 Awards (optional)

    Sections 8 and 9 are omitted entirely when data is absent.
    Missing fields render as red [MISSING: X] text via highlight_missing().
    Recency Rule is applied to experience bullets at generation time.

    Returns True on success, False on any exception.
    """
    try:
        page_w, page_h = A4
        margin = 2 * cm
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=margin,
            leftMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
        )

        styles = getSampleStyleSheet()
        teal = colors.HexColor("#1B6B6B")

        title_style = ParagraphStyle(
            "PrintTitle", parent=styles["Heading1"],
            fontName="Helvetica-Bold", fontSize=16, spaceAfter=4,
        )
        name_style = ParagraphStyle(
            "PrintName", parent=title_style, rightIndent=3.5 * cm,
        )
        section_style = ParagraphStyle(
            "PrintSection", parent=styles["Heading2"],
            fontName="Helvetica-Bold", fontSize=11,
            spaceBefore=10, spaceAfter=2, textColor=teal,
        )
        body_style = ParagraphStyle(
            "PrintBody", parent=styles["Normal"],
            fontName="Helvetica", fontSize=9.5, spaceAfter=3, leading=13,
        )
        contact_style = ParagraphStyle("PrintContact", parent=body_style, spaceAfter=2)
        contact_line_style = ParagraphStyle(
            "PrintContactLine", parent=contact_style, rightIndent=3.5 * cm,
        )
        role_title_style = ParagraphStyle(
            "PrintRoleTitle", parent=body_style,
            fontName="Helvetica-Bold", fontSize=9.5, spaceAfter=1,
        )
        role_meta_style = ParagraphStyle(
            "PrintRoleMeta", parent=body_style,
            fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=2,
        )
        bullet_style = ParagraphStyle(
            "PrintBullet", parent=body_style, leftIndent=12, bulletIndent=4,
        )

        def section_heading(title):
            return [
                Paragraph(title, section_style),
                HRFlowable(width="100%", thickness=0.5, color=teal, spaceAfter=3),
            ]

        pf = json_data.get("print_fields") or {}
        contact = json_data.get("contact") or {}

        # ── Photo setup (same pattern as ATS writer) ──────────────────────
        photo_io = None
        if photo_bytes:
            _raw = process_photo_for_pdf(photo_bytes)
            if _raw:
                try:
                    ImageReader(_raw)
                    _raw.seek(0)
                    photo_io = _raw
                except Exception as e:
                    logger.warning("Print PDF photo rejected: %s", e)

        def _draw_photo_first_page(canvas, doc):
            if not photo_io:
                return
            img_w = img_h = 3 * cm
            radius = 0.2 * cm
            x = page_w - margin - img_w
            y = page_h - margin - img_h
            canvas.saveState()
            p = canvas.beginPath()
            p.roundRect(x, y, img_w, img_h, radius)
            canvas.clipPath(p, stroke=0)
            photo_io.seek(0)
            canvas.drawImage(ImageReader(photo_io), x, y, img_w, img_h)
            canvas.restoreState()

        elements = []

        # ── Section 1 — Personal Details ─────────────────────────────────
        name_text = highlight_missing(json_data.get("candidate_name") or "[MISSING: Name]")
        elements.append(Paragraph(name_text, name_style if photo_io else title_style))

        phone = contact.get("phone") or "[MISSING: Phone]"
        email = contact.get("email") or "[MISSING: Email]"
        contact_line = highlight_missing(f"{phone} | {email}")
        elements.append(Paragraph(contact_line, contact_line_style if photo_io else contact_style))

        gender = pf.get("gender") or "[MISSING: Gender]"
        dob = pf.get("dob") or "[MISSING: Date of Birth]"
        age = pf.get("age") or ""
        city = pf.get("city") or "[MISSING: City]"
        open_relocate = pf.get("open_to_relocate", False)
        notice = pf.get("notice_period") or "[MISSING: Notice Period]"

        dob_age = f"{dob} (Age: {age})" if age else dob
        city_text = f"{city} | Open to Relocate" if open_relocate else city

        for label, value in [
            ("Gender", gender),
            ("DOB", dob_age),
            ("City", city_text),
            ("Notice Period", notice),
        ]:
            elements.append(Paragraph(
                highlight_missing(f"<b>{label}:</b> {value}"),
                body_style,
            ))

        elements.append(Spacer(1, 6))

        # ── Section 2 — Profile Links ─────────────────────────────────────
        elements.extend(section_heading("Profile Links"))
        linkedin = contact.get("linkedin") or "[MISSING: LinkedIn]"
        elements.append(Paragraph(highlight_missing(f"<b>LinkedIn:</b> {linkedin}"), body_style))
        portfolio = pf.get("portfolio_url") or ""
        if portfolio:
            elements.append(Paragraph(highlight_missing(f"<b>Portfolio:</b> {portfolio}"), body_style))

        # ── Section 3 — Professional Summary ─────────────────────────────
        summary = json_data.get("summary") or ""
        if summary:
            elements.extend(section_heading("Professional Summary"))
            elements.append(Paragraph(highlight_missing(summary), body_style))

        # ── Section 4 — Skills ────────────────────────────────────────────
        core_skills = pf.get("core_skills") or []
        tools = pf.get("tools_platforms") or []
        soft = pf.get("soft_skills") or []
        psychometric = pf.get("psychometric_type") or "[MISSING: Psychometric Type]"

        if core_skills or tools or soft:
            elements.extend(section_heading("Skills"))
            if core_skills:
                elements.append(Paragraph(
                    highlight_missing(f"<b>Core Technical:</b> {', '.join(core_skills[:5])}"),
                    body_style,
                ))
            if tools:
                elements.append(Paragraph(
                    highlight_missing(f"<b>Tools & Platforms:</b> {', '.join(tools[:5])}"),
                    body_style,
                ))
            if soft:
                elements.append(Paragraph(
                    highlight_missing(f"<b>Soft Skills:</b> {', '.join(soft[:5])}"),
                    body_style,
                ))
            elements.append(Paragraph(
                highlight_missing(f"<b>Psychometric Type:</b> {psychometric}"),
                body_style,
            ))

        # ── Section 5 — Professional Experience ──────────────────────────
        exp_list = json_data.get("experience") or []
        if exp_list:
            elements.extend(section_heading("Professional Experience"))
            for exp in _apply_recency_rule(exp_list):
                title = highlight_missing(exp.get("title") or "")
                company = highlight_missing(exp.get("company") or "")
                role_city = highlight_missing(exp.get("city") or "")
                dates = highlight_missing(exp.get("dates") or "")
                company_intro = highlight_missing(exp.get("company_intro") or "")

                meta_parts = [p for p in [company, role_city, dates] if p]
                block = [
                    Paragraph(title, role_title_style),
                    Paragraph(" | ".join(meta_parts), role_meta_style),
                ]
                if company_intro:
                    block.append(Paragraph(f"<i>{company_intro}</i>", role_meta_style))
                for b in exp.get("bullets") or []:
                    block.append(Paragraph(f"• {highlight_missing(b)}", bullet_style))
                elements.append(KeepTogether(block))
                elements.append(Spacer(1, 5))

        # ── Section 6 — Education ─────────────────────────────────────────
        edu_list = json_data.get("education") or []
        if edu_list:
            elements.extend(section_heading("Education"))
            for edu in edu_list:
                degree = highlight_missing(edu.get("degree") or "")
                inst = highlight_missing(edu.get("institution") or "")
                year = highlight_missing(edu.get("year") or "")
                elements.append(Paragraph(f"<b>{degree}</b>, {inst} ({year})", body_style))

        # ── Section 7 — Languages ─────────────────────────────────────────
        languages = pf.get("languages") or []
        if languages:
            elements.extend(section_heading("Languages"))
            parts = [
                f"{highlight_missing(la.get('language') or '')} — "
                f"{highlight_missing(la.get('proficiency') or '')}"
                for la in languages
            ]
            elements.append(Paragraph(" | ".join(parts), body_style))

        # ── Section 8 — Certifications (conditional) ─────────────────────
        certs = pf.get("certifications") or []
        if certs:
            elements.extend(section_heading("Certifications"))
            for cert in certs:
                name = highlight_missing(cert.get("name") or "")
                issuer = highlight_missing(cert.get("issuing_body") or "")
                year = highlight_missing(cert.get("year") or "")
                elements.append(Paragraph(f"{name} | {issuer} | {year}", body_style))

        # ── Section 9 — Awards & Recognition (optional) ──────────────────
        awards = pf.get("awards") or []
        if awards:
            elements.extend(section_heading("Awards & Recognition"))
            for award in awards:
                elements.append(Paragraph(highlight_missing(str(award)), body_style))

        doc.build(elements, onFirstPage=_draw_photo_first_page)

        buffer.seek(0)
        output_path.write_bytes(buffer.read())
        buffer.close()

        logger.info("Successfully generated Print PDF: %s", output_path)
        return True

    except Exception as e:
        logger.error("Failed to generate Print PDF: %s", e)
        return False
