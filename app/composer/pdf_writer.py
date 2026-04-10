import io
import logging
import pathlib
import re

import fitz  # PyMuPDF

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Flowable, KeepTogether
from reportlab.lib.utils import ImageReader

from .photo_handler import process_photo_for_pdf

logger = logging.getLogger(__name__)

def highlight_missing(text: str) -> str:
    """Replaces [MISSING: field] with a red colored version for ReportLab."""
    if not text:
        return ""
    # ReportLab Paragraph supports <font color="...">text</font>
    return re.sub(
        r'(\[MISSING[^\]]*\])',
        r'<font color="red">\1</font>',
        text
    )

def generate_resume_pdf(json_data: dict, photo_bytes: bytes | None, output_path: pathlib.Path) -> bool:
    """
    Composes a PDF resume given the LLM JSON output and optionally a photo.
    Layout: 
      - Top-right 3x3cm photo (if present)
      - Header (Name, contact)
      - Summary, Experience, Education, Skills
    Max 2 pages, 2cm margins.
    Returns True if generated successfully, else False.
    """
    try:
        page_w, page_h = A4
        margin = 2 * cm
        # Build to in-memory buffer first, then enforce 2-page cap
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
        # Create base styles using Helvetica
        title_style = ParagraphStyle(
            'ResumeTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            spaceAfter=6
        )
        contact_style = ParagraphStyle(
            'ResumeContact',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            spaceAfter=12
        )
        section_style = ParagraphStyle(
            'ResumeSection',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            spaceBefore=12,
            spaceAfter=2,
            textColor=colors.HexColor("#1B6B6B")
        )
        body_style = ParagraphStyle(
            'ResumeBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            spaceAfter=4,
            leading=14
        )
        bullet_style = ParagraphStyle(
            'ResumeBullet',
            parent=body_style,
            leftIndent=15,
            bulletIndent=5
        )
        role_title_style = ParagraphStyle(
            'RoleTitle',
            parent=body_style,
            fontName='Helvetica-Bold',
            fontSize=10,
            spaceAfter=1,
        )
        role_meta_style = ParagraphStyle(
            'RoleMeta',
            parent=body_style,
            fontName='Helvetica',
            fontSize=9.5,
            textColor=colors.HexColor("#555555"),
            spaceAfter=4,
        )
        name_style = ParagraphStyle(
            'ResumeName',
            parent=title_style,
            rightIndent=3.5 * cm,
        )
        contact_line_style = ParagraphStyle(
            'ResumeContactLine',
            parent=contact_style,
            rightIndent=3.5 * cm,
        )

        teal = colors.HexColor("#1B6B6B")

        def section_heading(title):
            """Return a section heading Paragraph followed by a teal HRFlowable divider."""
            return [
                Paragraph(title, section_style),
                HRFlowable(width="100%", thickness=0.5, color=teal, spaceAfter=4),
            ]

        class LeftBorderFlowable(Flowable):
            """Renders bullet paragraphs with a teal vertical bar on the left."""
            def __init__(self, paragraphs, bar_color=None, bar_width=2, indent=10):
                Flowable.__init__(self)
                self._paragraphs = paragraphs
                self._bar_color = bar_color if bar_color is not None else teal
                self._bar_width = bar_width
                self._indent = indent
                self._avail_width = 0
                self._heights = []

            def wrap(self, availWidth, availHeight):
                self._avail_width = availWidth - self._indent
                self._heights = [
                    p.wrap(self._avail_width, availHeight)[1]
                    for p in self._paragraphs
                ]
                self.height = sum(self._heights)
                self.width = availWidth
                return self.width, self.height

            def draw(self):
                c = self.canv
                y = self.height
                for p, h in zip(self._paragraphs, self._heights):
                    y -= h
                    p.drawOn(c, self._indent, y)
                c.setStrokeColor(self._bar_color)
                c.setLineWidth(self._bar_width)
                c.line(0, 0, 0, self.height)

        elements = []

        # Build name & contact text
        name_text = highlight_missing(json_data.get('candidate_name', '[MISSING: Name]'))
        contact = json_data.get('contact', {})
        email = contact.get('email', '') or '[MISSING: Email]'
        phone = contact.get('phone', '') or '[MISSING: Phone]'
        linkedin = contact.get('linkedin', '') or '[MISSING: LinkedIn]'
        contact_text = highlight_missing(f"{email} | {phone} | {linkedin}")

        # Prepare photo for canvas callback (captured in closure)
        photo_io = None
        if photo_bytes:
            _raw_photo = process_photo_for_pdf(photo_bytes)
            if _raw_photo:
                try:
                    ImageReader(_raw_photo)  # validate image is readable
                    _raw_photo.seek(0)
                    photo_io = _raw_photo
                except Exception as e:
                    logger.warning(f"Photo rejected (unreadable image): {e}")
                    photo_io = None

        def _draw_photo_first_page(canvas, doc):
            """Draw rounded photo at absolute top-right on page 1 only."""
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

        if photo_io:
            elements.append(Paragraph(name_text, name_style))
            elements.append(Paragraph(contact_text, contact_line_style))
        else:
            elements.append(Paragraph(name_text, title_style))
            elements.append(Paragraph(contact_text, contact_style))

        elements.append(Spacer(1, 10))

        # Summary
        summary = json_data.get('summary', '')
        if summary:
            elements.extend(section_heading("Summary"))
            elements.append(Paragraph(highlight_missing(summary), body_style))
            
        # Experience
        exp_list = json_data.get('experience', [])
        if exp_list:
            elements.extend(section_heading("Experience"))
            for exp in exp_list:
                title = highlight_missing(exp.get('title', ''))
                company = highlight_missing(exp.get('company', ''))
                dates = highlight_missing(exp.get('dates', ''))

                role_title_para = Paragraph(title, role_title_style)
                role_meta_para = Paragraph(f"{company} | {dates}", role_meta_style)

                bullet_paras = [
                    Paragraph(f"• {highlight_missing(b)}", bullet_style)
                    for b in exp.get('bullets', [])
                ]
                border_block = LeftBorderFlowable(bullet_paras) if bullet_paras else Spacer(1, 4)

                elements.append(KeepTogether([role_title_para, role_meta_para, border_block]))
                elements.append(Spacer(1, 6))

        # Education
        edu_list = json_data.get('education', [])
        if edu_list:
            elements.extend(section_heading("Education"))
            for edu in edu_list:
                degree = highlight_missing(edu.get('degree', ''))
                inst = highlight_missing(edu.get('institution', ''))
                year = highlight_missing(edu.get('year', ''))
                edu_text = f"<b>{degree}</b>, {inst} ({year})"
                elements.append(Paragraph(edu_text, body_style))
                
        # Skills
        skills = json_data.get('skills', [])
        if skills:
            elements.extend(section_heading("Skills"))
            skills_text = highlight_missing(", ".join(skills))
            elements.append(Paragraph(skills_text, body_style))

        doc.build(elements, onFirstPage=_draw_photo_first_page)

        buffer.seek(0)
        pdf_doc = fitz.open(stream=buffer.read(), filetype="pdf")
        buffer.close()
        try:
            if len(pdf_doc) > 2:
                logger.warning(
                    f"Resume exceeded 2 pages ({len(pdf_doc)} pages); truncating to 2."
                )
                while len(pdf_doc) > 2:
                    pdf_doc.delete_page(len(pdf_doc) - 1)
            pdf_doc.save(str(output_path))
        finally:
            pdf_doc.close()

        logger.info(f"Successfully generated PDF: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        return False
