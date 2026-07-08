"""
Exports the merged DDR (Detailed Diagnostic Report) data to PDF.

The generated report always follows this structure:
  1. Property Issue Summary
  2. Area-wise Observations (with supporting images placed under each area)
  3. Probable Root Cause (summary, cross-referenced to observations)
  4. Severity Assessment (with reasoning)
  5. Recommended Actions
  6. Additional Notes
  7. Missing or Unclear Information (explicitly "Not Available" when nothing was found)

Design notes:
  - Every text field falls back to "Not Available" rather than being left blank
    or omitted, per the "do not invent facts" / "flag missing info" requirement.
  - Every image reference is validated (file exists AND is a real, openable
    image) before being embedded. If a referenced image is missing or
    unreadable, the report prints "Image Not Available" instead of failing.
  - Conflicts detected between the inspection and thermal reports are always
    surfaced explicitly, never silently dropped.
"""
import os
import logging
from config import settings
from PIL import Image as PILImage
from fpdf import FPDF

logger = logging.getLogger(__name__)

NA = "Not Available"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _get_image_path(image_filename):
    if not image_filename:
        return None
    path = os.path.join(settings.STATIC_DIR, image_filename)
    return path if os.path.exists(path) else None


def _valid_image_path(image_filename):
    """Only returns a path if the file exists AND PIL can actually open it."""
    path = _get_image_path(image_filename)
    if not path:
        return None
    try:
        with PILImage.open(path) as im:
            im.verify()
        return path
    except Exception as e:
        logger.warning(f"Skipping missing/corrupt image '{image_filename}': {e}")
        return None


def _valid_images(images, limit=None):
    out = []
    for img in images or []:
        p = _valid_image_path(img)
        if p:
            out.append(p)
        if limit and len(out) >= limit:
            break
    return out


def _fmt(value, default=NA):
    """Coerce any missing/empty value to the standard 'Not Available' label."""
    if value is None:
        return default
    if isinstance(value, str) and not value.strip():
        return default
    if isinstance(value, (list, dict)) and not value:
        return default
    return value


def _area_of(obs):
    loc = (obs.get("location") or "").strip()
    return loc if loc else "General / Unspecified Area"


def _group_by_area(observations):
    """Groups observations by location, preserving first-seen order."""
    groups, order = {}, []
    for obs in observations:
        area = _area_of(obs)
        if area not in groups:
            groups[area] = []
            order.append(area)
        groups[area].append(obs)
    return [(area, groups[area]) for area in order]


def _additional_notes(report_data):
    """Derives the 'Additional Notes' section from inspector notes, stats and validation flags."""
    notes = []
    for obs in report_data.get("observations", []):
        note = obs.get("inspector_notes")
        if note and str(note).strip() and note not in notes:
            notes.append(str(note).strip())

    stats = report_data.get("statistics", {})
    total_obs = stats.get("total_observations", len(report_data.get("observations", [])))
    total_imgs = stats.get("total_images", 0)
    notes.append(
        f"This DDR cross-references {total_obs} observation(s) and {total_imgs} extracted "
        f"image(s) from the inspection and thermal reports."
    )

    validation = report_data.get("validation", {})
    if validation and not validation.get("is_valid", True) and validation.get("errors"):
        notes.append(
            "Automated quality checks flagged the following for manual review: "
            + "; ".join(validation["errors"][:5])
        )
    return notes


def _severity_rank(sev):
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(str(sev or "").lower(), 4)


# --------------------------------------------------------------------------- #
# PDF (fpdf2)
# --------------------------------------------------------------------------- #

_PDF_CHAR_MAP = {
    "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-",
    "\u00a0": " ",
}


def _pdf_safe_text(text):
    """
    fpdf2's built-in core fonts (helvetica, etc.) only support latin-1.
    AI-generated text routinely contains em-dashes, curly quotes, bullets,
    etc. which would otherwise crash the whole export. Normalize common
    "smart" punctuation to ASCII, then replace anything else that still
    can't be encoded instead of raising.
    """
    text = str(text)
    for uni, ascii_eq in _PDF_CHAR_MAP.items():
        text = text.replace(uni, ascii_eq)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _pdf_heading(pdf, text, size=14):
    pdf.set_font("helvetica", "B", size)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 10, _pdf_safe_text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)


def _pdf_para(pdf, text, bold=False, size=11):
    """Safe multi_cell wrapper — always resets the cursor to the left margin
    afterwards. Forgetting this is what previously crashed every PDF export
    with 'Not enough horizontal space to render a single character', because
    fpdf2's multi_cell leaves the cursor at the right edge by default."""
    pdf.set_font("helvetica", "B" if bold else "", size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 6, _pdf_safe_text(text), new_x="LMARGIN", new_y="NEXT")


def _pdf_add_image(pdf, img_path, max_w=90):
    try:
        with PILImage.open(img_path) as im:
            w, h = im.size
        max_w = min(max_w, pdf.w - pdf.l_margin - pdf.r_margin)
        display_h = max_w * (h / w) if w else 40
        if pdf.get_y() + display_h > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf.set_x(pdf.l_margin)
        pdf.image(img_path, x=pdf.l_margin, w=max_w)
        pdf.set_x(pdf.l_margin)
        pdf.ln(2)
    except Exception as e:
        logger.error(f"Failed to add image {img_path} to PDF: {e}")
        _pdf_para(pdf, "[Image could not be rendered]")


def generate_pdf_report(report_data: dict, filename: str = "report.pdf") -> str:
    filepath = os.path.join(settings.OUTPUT_DIR, filename)
    summary = report_data.get("property_summary", {}) or {}
    observations = report_data.get("observations", []) or []
    recommendations = report_data.get("recommendations", []) or []
    conflicts = report_data.get("conflicts", []) or []
    missing_info = report_data.get("missing_information", []) or []

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("helvetica", "B", 18)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 12, _pdf_safe_text("Detailed Diagnostic Report (DDR)"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # 1. Property Issue Summary
    _pdf_heading(pdf, "1. Property Issue Summary")
    _pdf_para(pdf, f"Property: {_fmt(summary.get('property_name'))}")
    _pdf_para(pdf, f"Address: {_fmt(summary.get('address'))}")
    _pdf_para(pdf, f"Property Type: {_fmt(summary.get('property_type'))}")
    _pdf_para(pdf, f"Inspection Date: {_fmt(summary.get('inspection_date'))}")
    _pdf_para(pdf, f"Overall Condition: {_fmt(summary.get('overall_condition'))}")
    if summary.get("overall_condition_reason"):
        _pdf_para(pdf, f"Reason: {summary.get('overall_condition_reason')}")
    _pdf_para(pdf, f"Total Issues Identified: {_fmt(summary.get('total_issues_count', len(observations)))}")
    key_concerns = summary.get("key_concerns") or []
    if key_concerns:
        _pdf_para(pdf, "Key Concerns:", bold=True)
        for c in key_concerns:
            _pdf_para(pdf, f"  - {c}")
    pdf.ln(3)

    # 2. Area-wise Observations
    _pdf_heading(pdf, "2. Area-wise Observations")
    for area, obs_list in _group_by_area(observations):
        _pdf_para(pdf, area, bold=True, size=13)
        for obs in obs_list:
            _pdf_para(pdf, f"[{obs.get('observation_id', NA)}] {_fmt(obs.get('issue'))}", bold=True)
            if obs.get("engineering_finding"):
                _pdf_para(pdf, f"Technical Finding: {obs.get('engineering_finding')}")
            details = []
            for label, key in [("Measurements", "measurements"), ("Moisture", "moisture"),
                                ("Crack Width", "crack_width"), ("Temperature", "temperatures")]:
                if obs.get(key):
                    details.append(f"{label}: {obs.get(key)}")
            if details:
                _pdf_para(pdf, " | ".join(details))
            _pdf_para(pdf, f"Source: {', '.join(obs.get('supporting_documents') or []) or NA}")

            images = _valid_images(obs.get("supporting_images"), limit=3)
            if images:
                for img_path in images:
                    _pdf_add_image(pdf, img_path)
            else:
                _pdf_para(pdf, "Image Not Available")
            pdf.ln(2)
    pdf.ln(2)

    # 3. Probable Root Cause
    _pdf_heading(pdf, "3. Probable Root Cause")
    if observations:
        for obs in observations:
            _pdf_para(pdf, f"[{obs.get('observation_id', NA)}] {_area_of(obs)}: {_fmt(obs.get('root_cause'))}")
    else:
        _pdf_para(pdf, NA)
    pdf.ln(2)

    # 4. Severity Assessment (with reasoning)
    _pdf_heading(pdf, "4. Severity Assessment")
    if observations:
        for obs in sorted(observations, key=lambda o: _severity_rank(o.get("severity"))):
            sev = str(_fmt(obs.get("severity"))).upper()
            _pdf_para(pdf, f"[{obs.get('observation_id', NA)}] {_area_of(obs)} — Severity: {sev}", bold=True)
            _pdf_para(pdf, f"Reasoning: {_fmt(obs.get('severity_reason'))}")
    else:
        _pdf_para(pdf, NA)
    pdf.ln(2)

    # 5. Recommended Actions
    _pdf_heading(pdf, "5. Recommended Actions")
    if recommendations:
        for rec in recommendations:
            _pdf_para(pdf,
                      f"- ({_fmt(rec.get('severity')).upper() if rec.get('severity') else NA}) "
                      f"{_fmt(rec.get('issue'))}: {_fmt(rec.get('recommendation'))} "
                      f"[Confidence: {_fmt(rec.get('confidence'))}]")
    else:
        _pdf_para(pdf, NA)
    pdf.ln(2)

    # 6. Additional Notes
    _pdf_heading(pdf, "6. Additional Notes")
    for note in _additional_notes(report_data):
        _pdf_para(pdf, f"- {note}")
    if conflicts:
        _pdf_para(pdf, "Conflicts Between Reports:", bold=True)
        for c in conflicts:
            _pdf_para(pdf, f"- {c.get('reason', NA)} (Involves: {', '.join(c.get('documents_involved') or [])}). "
                            f"Recommended verification: {c.get('recommended_manual_verification', NA)}")
    pdf.ln(2)

    # 7. Missing or Unclear Information
    _pdf_heading(pdf, "7. Missing or Unclear Information")
    if missing_info:
        for item in missing_info:
            _pdf_para(pdf, f"- {item}")
    else:
        _pdf_para(pdf, NA)

    pdf.output(filepath)
    return filepath


