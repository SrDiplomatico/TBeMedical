"""PDF reader for extracting AcroForm fields from I-693 PDFs."""

import fitz  # PyMuPDF
from datetime import datetime, date
from pathlib import Path
from typing import Any

from src.models.i693_form import (
    I693Form,
    ApplicantInfo,
    MedicalExamination,
    VaccinationHistory,
    CivilSurgeonInfo,
)
from src.parser.field_mapping import I693_FIELD_MAP, is_checkbox_checked


# ---------------------------------------------------------------------------
# Coordinate zones for I-693 Edition 01/20/25 (standard 612×792 pt page).
# Used as fallback when the PDF has been flattened (no AcroForm widgets).
# Format: field_name → (page_index, x0, y0, x1, y1)
# ---------------------------------------------------------------------------
_I693_FLAT_ZONES: dict[str, tuple[int, float, float, float, float]] = {
    # ── Page 1 (index 0): Applicant Info ───────────────────────────────────
    # Name row: labels at y≈178, data at y≈193-206
    "form1[0].#subform[0].Pt1Line1a_FamilyName[0]":            (0,  36, 193, 270, 207),
    "form1[0].#subform[0].Pt1Line1b_GivenName[0]":             (0, 270, 193, 444, 207),
    "form1[0].#subform[0].Pt1Line1c_MiddleName[0]":            (0, 444, 193, 576, 207),
    # Address
    "form1[0].#subform[0].Pt1Line2_StreetNumberName[0]":       (0,  36, 283, 410, 297),
    # Apt./Ste./Flr. number sits right of the three unit checkboxes (x 410-464)
    "form1[0].#subform[0].Pt1Line2_AptSteFlrNumber[0]":        (0, 464, 283, 576, 297),
    "form1[0].#subform[0].P1Line2_CityOrTown[0]":              (0,  36, 319, 410, 333),
    "form1[0].#subform[0].P1Line2_State[0]":                   (0, 410, 319, 464, 333),
    "form1[0].#subform[0].P1Line2_ZipCode[0]":                 (0, 464, 319, 576, 333),
    "form1[0].#subform[0].P1Line2_Country[0]":                 (0, 340, 355, 576, 369),
    # Other info
    "form1[0].#subform[0].Pt1Line3_DateOfBirth[0]":            (0, 196, 409, 330, 423),
    "form1[0].#subform[0].Pt1Line3_CityTownVillageofBirth[0]": (0, 330, 409, 576, 423),
    "form1[0].#subform[0].Pt1Line3_CountryofBirth[0]":         (0,  36, 444, 330, 462),
    # A-Number (may be empty; zone starts after the printed "A-" label at x≈374)
    "form1[0].#subform[0].#area[0].Pt1Line3e_AlienNumber[0]":  (0, 395, 444, 576, 462),

    # ── Page 2 (index 1): Parts 2-3 — Applicant contact info ──────────────
    # Phone label at y≈148-161, value at y≈163-176
    "form1[0].#subform[1].Pt2Line3_DaytimePhone[0]":           (1,  36, 163, 300, 177),
    # Mobile phone column starts at x≈311
    "form1[0].#subform[1].Pt2Line4_Mobilephone[0]":            (1, 311, 163, 576, 177),
    # Email label at y≈184-197, value at y≈199-212
    "form1[0].#subform[1].Pt2Line5_EmailAddress[0]":           (1,  36, 199, 576, 213),

    # ── Page 3 (index 2): Part 5 — Applicant ID ────────────────────────────
    "form1[0].#subform[2].Pt5Line1_ApplicantFormOfID[0]":      (2,  36, 685, 420, 699),
    "form1[0].#subform[2].Pt5Line2_IDNumber[0]":               (2,  36, 721, 420, 735),

    # ── Page 4 (index 3): Parts 6-7 — Exam date + Civil Surgeon ───────────
    # Exam date (Part 6 §2): label "(mm/dd/yyyy)" ends at x≈111, value at x≈116
    "form1[0].#subform[3].Pt6Line2_DateoExam[0]":              (3, 112, 187, 200, 201),
    # Civil surgeon name row: labels at y≈340, data at y≈355-368
    "form1[0].#subform[3].Pt7Line1_FamilyName[0]":             (3,  36, 355, 275, 369),
    "form1[0].#subform[3].Pt7Line1_GivenName[0]":              (3, 275, 355, 437, 369),
    "form1[0].#subform[3].Pt7Line1_MiddleName[0]":             (3, 437, 355, 576, 369),
    # CSID: "designation)" ends at x≈254, value starts at x≈260
    "form1[0].#subform[3].Pt7Line1_CivilSurgeonID[0]":         (3, 255, 391, 350, 408),
    # Practice name
    "form1[0].#subform[3].Pt7Line2_MedPracticeName[0]":        (3,  36, 427, 576, 441),
    # Physical address
    "form1[0].#subform[3].Pt7Line3_StreetNumberName[0]":       (3,  36, 493, 410, 507),
    "form1[0].#subform[3].Pt7Line3_AptSteFlrNumber[0]":        (3, 464, 493, 576, 507),
    "form1[0].#subform[3].Pt7Line3_CityOrTown[0]":             (3,  36, 529, 410, 543),
    "form1[0].#subform[3].Pt7Line3_State[0]":                  (3, 410, 529, 464, 543),
    "form1[0].#subform[3].Pt7Line3_ZipCode[0]":                (3, 464, 529, 576, 543),
    # Mailing address (same structure, y offset +100)
    "form1[0].#subform[3].Pt7Line4_StreetNumberName[0]":       (3,  36, 595, 410, 609),
    "form1[0].#subform[3].Pt7Line4_CityOrTown[0]":             (3,  36, 631, 410, 645),
    "form1[0].#subform[3].Pt7Line4_State[0]":                  (3, 410, 631, 464, 645),
    "form1[0].#subform[3].Pt7Line4_ZipCode[0]":                (3, 464, 631, 576, 645),

    # ── Page 6 (index 5): Part 8.1.A — TB screening dates ─────────────────
    # IGRA "Date Blood Sample Drawn" (QuantiFERON column, left)
    "form1[0].#subform[5].Pt8Line1A1_QFDate[0]":                (5, 120, 288, 310, 304),
    # Chest X-ray taken / read dates (Part 8.1.A(3))
    "form1[0].#subform[5].Pt8Line1A3_XrayTakenDate[0]":         (5,  88, 515, 292, 532),
    "form1[0].#subform[5].Pt8Line1A3_XrayReadDate[0]":          (5, 298, 515, 500, 532),

    # ── Page 7 (index 6): Part 8.1.A(7) — TB remarks ──────────────────────
    # Four ruled lines at y = 540 / 558 / 576 / 594
    "form1[0].#subform[6].Pt8Line1A7_Remarks[0]":               (6,  90, 524, 576, 595),
}

# T-Spot "Date Blood Sample Drawn" (right column on page 6).  The I-693 field
# map has only one IGRA date field, so this zone is used when T-Spot is the
# selected IGRA and the QuantiFERON column is blank.
_TSPOT_DATE_ZONE: tuple[int, float, float, float, float] = (5, 420, 288, 570, 304)

# ---------------------------------------------------------------------------
# Part 1, Line 2: "Apt.  Ste.  Flr." unit-type checkboxes.  Three boxes sit
# between the street field (ends x≈410) and the unit number field (starts
# x≈464), on the street-address row.  Ordered left-to-right.
# ---------------------------------------------------------------------------
_UNIT_TYPES_LEFT_TO_RIGHT = ("APT", "STE", "FLR")
_UNIT_CHECKBOX_AREA = (405.0, 274.0, 472.0, 304.0)  # page 1 (index 0)

# ---------------------------------------------------------------------------
# Part 8 (Civil Surgeon Worksheet) checkbox positions for flattened I-693.
# Every checkbox is a 10.5×10.5 pt outer square; a *checked* box additionally
# contains a 6.5×6.5 pt inner square offset by 2 pt.
# Format: logical_name → (page_index, outer_x0, outer_y0)
# ---------------------------------------------------------------------------
_PART8_FLAT_CHECKBOXES: dict[str, tuple[int, float, float]] = {
    # ── Page 6 (index 5): Part 8.1.A(1) — IGRA ────────────────────────────
    "igra_not_administered":     (5,  91.5, 222.0),
    "igra_quantiferon":          (5, 108.9, 258.0),
    "igra_tspot":                (5, 330.9, 258.0),
    "igra_result_negative":      (5, 162.9, 312.0),
    "igra_result_positive":      (5, 162.9, 330.0),
    "igra_result_indeterminate": (5, 162.9, 348.0),

    # ── Page 6: Part 8.1.A(2) — chest X-ray determination ─────────────────
    "xray_not_required":         (5,  90.9, 384.0),
    "xray_req_screening":        (5,  90.9, 402.0),
    "xray_req_tb_signs":         (5,  90.9, 420.0),
    "xray_req_igra_exception":   (5,  90.9, 438.0),

    # ── Page 6: Part 8.1.A(3) — chest X-ray result ────────────────────────
    "xray_normal":               (5, 132.9, 540.0),
    "xray_abnormal":             (5, 132.9, 558.0),

    # ── Page 6: Part 8.1.A(3) — abnormal findings (left / right columns) ──
    "xray_infiltrate":           (5, 150.9, 576.0),
    "xray_reticular":            (5, 150.9, 594.0),
    "xray_cavity":               (5, 150.9, 612.0),
    "xray_nodules":              (5, 150.9, 630.0),
    "xray_pleural":              (5, 150.9, 660.0),
    "xray_hilar":                (5, 150.9, 678.0),
    "xray_miliary":              (5, 348.9, 576.0),
    "xray_linear":               (5, 348.9, 594.0),
    "xray_discrete_nodule":      (5, 348.9, 612.0),
    "xray_volume_loss":          (5, 348.9, 630.0),
    "xray_thick_pleural":        (5, 348.9, 660.0),
    "xray_other":                (5, 348.9, 678.0),

    # ── Page 7 (index 6): Part 8.1.A(4) — sputum smears/cultures decision ─
    "sputum_not_indicated":      (6,  90.9, 120.0),
    "sputum_signs_symptoms":     (6,  90.9, 138.0),
    "sputum_chest_xray":         (6,  90.9, 156.0),
    "sputum_hiv_extrapulm":      (6, 324.9, 120.0),
    "sputum_end_treatment":      (6, 324.9, 156.0),

    # ── Page 7: Part 8.1.A(6) — TB classification ─────────────────────────
    "tb_class_no_tb":            (6,  90.9, 426.0),
    "tb_class_a":                (6,  90.9, 444.0),
    "tb_class_b0":               (6,  90.9, 462.0),
    "tb_class_b1_pulm":          (6,  90.9, 480.0),
    "tb_class_b1_extrapulm":     (6, 252.9, 426.0),
    "tb_class_b2_ltbi":          (6, 252.9, 444.0),
    "tb_class_b_other":          (6, 252.9, 462.0),
}

# Abnormal-finding checkbox name → I693Form.examination attribute
_XRAY_FINDING_ATTRS = (
    "xray_infiltrate", "xray_reticular", "xray_cavity", "xray_nodules",
    "xray_pleural", "xray_hilar", "xray_miliary", "xray_linear",
    "xray_discrete_nodule", "xray_volume_loss", "xray_thick_pleural",
    "xray_other",
)

# ---------------------------------------------------------------------------
# Part 8.1.A(5) sputum smear / culture result tables (flattened I-693).
# Both tables live on page 7 (index 6) and are drawn as explicit stroked cell
# rectangles, so the grid below matches the cell borders exactly.
# `rows` are the (y0, y1) bands of the three data rows; `cols` are the (x0, x1)
# bands of each column.  `result_order` is the precedence used when more than
# one result column is marked.
# ---------------------------------------------------------------------------
_SPUTUM_SMEAR_TABLE: dict = {
    "page": 6,
    "rows": [(240.0, 257.9), (257.9, 275.9), (275.9, 293.8)],
    "cols": {
        "specimen_date": (102.5, 264.3),
        "result_date":   (264.3, 450.0),
        "POS":           (449.9, 516.0),
        "NEG":           (516.0, 576.0),
    },
    "result_order": ("POS", "NEG"),
}

_SPUTUM_CULTURE_TABLE: dict = {
    "page": 6,
    "rows": [(348.0, 366.0), (366.0, 384.0), (384.0, 402.0)],
    "cols": {
        "specimen_date": (102.0, 228.0),
        "result_date":   (228.0, 366.0),
        "POS":           (366.0, 414.0),
        "NEG":           (414.0, 462.0),
        "NTM":           (462.0, 510.0),
        "CNTAMNTD":      (510.0, 576.0),
    },
    "result_order": ("POS", "NTM", "CNTAMNTD", "NEG"),
}


def _extract_zone_text(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> str:
    """Extract and join all words within a rectangular clip zone."""
    clip = fitz.Rect(x0, y0, x1, y1)
    words = page.get_text("words", clip=clip)
    return " ".join(w[4] for w in sorted(words, key=lambda w: (w[1], w[0]))).strip()


def _detect_checked_checkbox(page: fitz.Page, outer: fitz.Rect) -> bool:
    """
    Return True if a checkbox (defined by its outer bounding rect) is checked.

    A checked checkbox in a flattened I-693 has a smaller outlined rectangle
    drawn strictly inside the outer checkbox rectangle.  The outer box itself
    is excluded by requiring the inner drawing to be at least 1 pt smaller on
    every side.
    """
    for d in page.get_drawings():
        r = d["rect"]
        # Must be strictly inside with at least 1pt margin (outer box excluded)
        if (r.x0 >= outer.x0 + 1 and r.y0 >= outer.y0 + 1
                and r.x1 <= outer.x1 - 1 and r.y1 <= outer.y1 - 1):
            return True
    return False


def _flat_checkbox_checked(page: fitz.Page, x: float, y: float,
                           tol: float = 3.0) -> bool:
    """
    Return True if the flattened checkbox whose outer square starts near
    (x, y) is checked.

    Locates the ~10.5 pt outer square within `tol` of the expected top-left
    corner, then tests it for an inner mark.  Returns False if no outer box
    is found at that location (guards against layout drift).
    """
    for d in page.get_drawings():
        r = d["rect"]
        if (abs(r.x0 - x) <= tol and abs(r.y0 - y) <= tol
                and 8 <= r.width <= 14 and 8 <= r.height <= 14):
            return _detect_checked_checkbox(page, r)
    return False


def _flat_cell_has_mark(page: fitz.Page, x0: float, y0: float,
                        x1: float, y1: float) -> bool:
    """
    Return True if a table result cell contains a mark.

    The I-693 stores sputum results as a text field holding 'X', so a flattened
    render puts a literal glyph in the cell.  Any non-whitespace text inside the
    cell counts as a mark ('X', 'x', a tick, etc.).  As a fallback, a small
    vector drawing strictly inside the cell (excluding the cell border itself)
    also counts.
    """
    if _extract_zone_text(page, x0 + 2, y0 + 2, x1 - 2, y1 - 2):
        return True

    for d in page.get_drawings():
        r = d["rect"]
        if (r.x0 >= x0 + 1 and r.y0 >= y0 + 1
                and r.x1 <= x1 - 1 and r.y1 <= y1 - 1):
            return True
    return False


def extract_sputum_results_from_flattened_pdf(pdf_path: str | Path) -> dict[str, str]:
    """
    Extract the Part 8.1.A(5) sputum smear and culture result tables from a
    flattened I-693 by reading each table cell by coordinate.

    Returns the same keys as extract_sputum_results():
      smear_specimen_date_N, smear_result_date_N, smear_result_N
      culture_specimen_date_N, culture_result_date_N, culture_result_N
    where N = 1..3.  Result codes are 'POS'/'NEG' for smears and
    'POS'/'NEG'/'NTM'/'CNTAMNTD' for cultures ('' when the row is blank).
    """
    doc = fitz.open(str(Path(pdf_path)))
    result: dict[str, str] = {}
    try:
        for prefix, table in (("smear", _SPUTUM_SMEAR_TABLE),
                              ("culture", _SPUTUM_CULTURE_TABLE)):
            page_idx = table["page"]
            if page_idx >= doc.page_count:
                continue
            page = doc[page_idx]
            cols = table["cols"]
            spec_x0, spec_x1 = cols["specimen_date"]
            res_x0, res_x1 = cols["result_date"]

            for row_idx, (ry0, ry1) in enumerate(table["rows"], start=1):
                result[f"{prefix}_specimen_date_{row_idx}"] = _extract_zone_text(
                    page, spec_x0 + 2, ry0 + 1, spec_x1 - 2, ry1 - 1
                )
                result[f"{prefix}_result_date_{row_idx}"] = _extract_zone_text(
                    page, res_x0 + 2, ry0 + 1, res_x1 - 2, ry1 - 1
                )

                code = ""
                for key in table["result_order"]:
                    cx0, cx1 = cols[key]
                    if _flat_cell_has_mark(page, cx0, ry0, cx1, ry1):
                        code = key
                        break
                result[f"{prefix}_result_{row_idx}"] = code
    finally:
        doc.close()

    print(f"DEBUG: Flattened sputum table extraction: {result}")
    return result


def detect_part8_from_flattened_pdf(pdf_path: str | Path) -> dict[str, str]:
    """
    Derive Part 8 (Civil Surgeon Worksheet) values from a flattened I-693 by
    reading its checkbox drawings.

    Returns a dict of I693Form.examination attribute names → values, ready to
    be applied with setattr().  Only keys that were positively detected are
    included, so callers can safely overlay it on top of AcroForm results.
    """
    doc = fitz.open(str(Path(pdf_path)))
    try:
        pages = list(doc)
        checked: dict[str, bool] = {}
        for name, (page_idx, x, y) in _PART8_FLAT_CHECKBOXES.items():
            if page_idx < len(pages):
                checked[name] = _flat_checkbox_checked(pages[page_idx], x, y)
    finally:
        doc.close()

    derived: dict[str, str] = {}

    # ── Part 8.1.A(1): IGRA test type ──────────────────────────────────────
    if checked.get("igra_quantiferon"):
        derived["tb_test_type"] = "QUANTIFERON"
    elif checked.get("igra_tspot"):
        derived["tb_test_type"] = "TSPOT"

    # ── Part 8.1.A(1): IGRA result ─────────────────────────────────────────
    if checked.get("igra_result_negative"):
        derived["igra_test_result"] = "N"
    elif checked.get("igra_result_positive"):
        derived["igra_test_result"] = "P"
    elif checked.get("igra_result_indeterminate"):
        derived["igra_test_result"] = "I"
    if "igra_test_result" in derived:
        derived["tb_skin_test_result"] = derived["igra_test_result"]

    # ── Part 8.1.A(2): chest X-ray determination ───────────────────────────
    if checked.get("xray_not_required"):
        derived["initial_tb_screening"] = "A"
    elif checked.get("xray_req_screening"):
        derived["initial_tb_screening"] = "B"
    elif checked.get("xray_req_tb_signs"):
        derived["initial_tb_screening"] = "C"
    elif checked.get("xray_req_igra_exception"):
        derived["initial_tb_screening"] = "D"

    # ── Part 8.1.A(3): chest X-ray result ──────────────────────────────────
    if checked.get("xray_normal"):
        derived["chest_xray_result"] = "N"
    elif checked.get("xray_abnormal"):
        derived["chest_xray_result"] = "A"

    # Abnormal findings are only meaningful when the result is Abnormal.
    if derived.get("chest_xray_result") == "A":
        for attr in _XRAY_FINDING_ATTRS:
            derived[attr] = "Yes" if checked.get(attr) else ""

    # ── Part 8.1.A(4): sputum smears and cultures decision ─────────────────
    sputum_reasons = (
        ("sputum_signs_symptoms", "signs_symptoms"),
        ("sputum_chest_xray", "chest_xray"),
        ("sputum_hiv_extrapulm", "hiv_extrapulm"),
        ("sputum_end_treatment", "end_treatment"),
    )
    selected_reason = next(
        (attr for attr, _ in sputum_reasons if checked.get(attr)), None
    )
    if checked.get("sputum_not_indicated"):
        derived["sputum_indicated"] = "NI"
        for attr, _ in sputum_reasons:
            derived[attr] = ""
    elif selected_reason:
        derived["sputum_indicated"] = "IND"
        for attr, _ in sputum_reasons:
            derived[attr] = "Yes" if attr == selected_reason else ""

    # ── Part 8.1.A(6): TB classification ───────────────────────────────────
    tb_class_map = (
        ("tb_class_no_tb", "NO_TB"),
        ("tb_class_a", "CLASS_A"),
        ("tb_class_b0", "B0_PULM"),
        ("tb_class_b1_pulm", "B1_PULM"),
        ("tb_class_b1_extrapulm", "B1_EXTRAPULM"),
        ("tb_class_b2_ltbi", "B2_LTBI"),
        ("tb_class_b_other", "B_OTHER"),
    )
    for name, code in tb_class_map:
        if checked.get(name):
            derived["tb_classification"] = code
            break

    return derived


def _detect_sex_from_flattened_page(page: fitz.Page) -> str:
    """
    Return 'M', 'F', or '' by inspecting checkbox drawings on page 1.

    Locates Male and Female checkbox outer rectangles by finding ~10×10 pt
    white-filled squares in the sex field area (x=60-170, y=408-425), then
    checks each for an inner mark.
    """
    sex_area = fitz.Rect(60, 408, 170, 425)
    checkbox_rects: list[fitz.Rect] = []

    for d in page.get_drawings():
        r = d["rect"]
        w, h = r.x1 - r.x0, r.y1 - r.y0
        # Outer checkbox: ~10×10 pt square in the sex area
        if (sex_area.contains(r) and 7 <= w <= 14 and 7 <= h <= 14):
            checkbox_rects.append(r)

    # Sort left-to-right: first = Male, second = Female
    checkbox_rects.sort(key=lambda r: r.x0)

    if len(checkbox_rects) >= 1 and _detect_checked_checkbox(page, checkbox_rects[0]):
        return "M"
    if len(checkbox_rects) >= 2 and _detect_checked_checkbox(page, checkbox_rects[1]):
        return "F"
    return ""


def _normalize_unit_type(value: str) -> str:
    """Map any spelling of the Apt./Ste./Flr. unit type to 'APT'/'STE'/'FLR'."""
    v = (value or "").replace("#20", " ").strip().upper().rstrip(".")
    if not v or v in ("OFF", "NO", "NONE", "0", "FALSE"):
        return ""
    if v.startswith("APT") or v.startswith("APARTMENT") or v == "1":
        return "APT"
    if v.startswith("STE") or v.startswith("SUITE") or v == "2":
        return "STE"
    if v.startswith("FLR") or v.startswith("FLOOR") or v.startswith("FL") or v == "3":
        return "FLR"
    return ""


def _split_unit_prefix(value: str) -> tuple[str, str]:
    """
    Split a unit-number string that already carries its own prefix.

    'APT 4B' -> ('APT', '4B'), 'Suite 100' -> ('STE', '100'), '8213' -> ('', '8213')
    """
    text = (value or "").strip()
    if not text:
        return ("", "")
    parts = text.split(None, 1)
    if len(parts) == 2:
        unit_type = _normalize_unit_type(parts[0])
        if unit_type:
            return (unit_type, parts[1].strip())
    return ("", text)


def _detect_unit_type_from_flattened_page(page: fitz.Page) -> str:
    """
    Return 'APT', 'STE', 'FLR', or '' by inspecting the Part 1 Line 2 unit
    checkbox drawings on a flattened page 1.
    """
    x0, y0, x1, y1 = _UNIT_CHECKBOX_AREA
    area = fitz.Rect(x0, y0, x1, y1)
    # Dedupe by x position: the same square may be drawn as separate fill/stroke paths
    by_x: dict[float, fitz.Rect] = {}

    for d in page.get_drawings():
        r = d["rect"]
        w, h = r.x1 - r.x0, r.y1 - r.y0
        if area.contains(r) and 7 <= w <= 14 and 7 <= h <= 14:
            by_x.setdefault(round(r.x0, 1), r)

    rects = [by_x[k] for k in sorted(by_x)]
    if len(rects) < len(_UNIT_TYPES_LEFT_TO_RIGHT):
        return ""

    for label, rect in zip(_UNIT_TYPES_LEFT_TO_RIGHT, rects):
        if _detect_checked_checkbox(page, rect):
            return label
    return ""


def detect_unit_type(pdf_path: str | Path, raw_fields: dict[str, str]) -> str:
    """
    Determine which of the Apt./Ste./Flr. boxes is checked in Part 1, Line 2.

    Returns 'APT', 'STE', 'FLR', or '' when none is marked.  Works for both
    AcroForm PDFs (all three widgets share the same field_value, so the checked
    box is identified by visual position) and flattened PDFs (checkbox marks
    are read from the page drawings).
    """
    pdf_path = Path(pdf_path)

    if _pdf_is_flattened(pdf_path):
        doc = fitz.open(str(pdf_path))
        try:
            if doc.page_count:
                return _detect_unit_type_from_flattened_page(doc[0])
        finally:
            doc.close()
        return ""

    visual_idx, on_state = extract_radio_button_selection_by_position(
        pdf_path, "Pt1Line2_Unit"
    )
    if 0 <= visual_idx < len(_UNIT_TYPES_LEFT_TO_RIGHT):
        return _UNIT_TYPES_LEFT_TO_RIGHT[visual_idx]

    # Fallback: some PDFs store the selected export value on every widget
    for value in (on_state, *(raw_fields.get(f"form1[0].#subform[0].Pt1Line2_Unit[{i}]", "")
                              for i in range(3))):
        unit_type = _normalize_unit_type(value)
        if unit_type:
            return unit_type
    return ""


def extract_fields_from_flattened_pdf(pdf_path: str | Path) -> dict[str, str]:
    """
    Extract I-693 field values from a flattened (non-AcroForm) PDF using
    fixed coordinate zones calibrated to the I-693 Edition 01/20/25 layout.

    Returns a dict with the same keys as extract_raw_fields() so the rest of
    the pipeline is unchanged.
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    fields: dict[str, str] = {}

    try:
        pages = list(doc)
        for field_name, (page_idx, x0, y0, x1, y1) in _I693_FLAT_ZONES.items():
            if page_idx >= len(pages):
                continue
            value = _extract_zone_text(pages[page_idx], x0, y0, x1, y1)
            if value:
                fields[field_name] = value

        # Detect sex/gender from checkbox drawings on page 1
        if pages:
            sex = _detect_sex_from_flattened_page(pages[0])
            if sex:
                fields["form1[0].#subform[0].Pt1Line3_Gender[0]"] = sex
                print(f"DEBUG: Flattened PDF sex detection: '{sex}'")

        # If T-Spot was the IGRA used, its blood-draw date sits in the right
        # column.  The I-693 field map has only one IGRA date field, so reuse
        # the QuantiFERON key.
        igra_date_key = "form1[0].#subform[5].Pt8Line1A1_QFDate[0]"
        ts_page, tx0, ty0, tx1, ty1 = _TSPOT_DATE_ZONE
        if not fields.get(igra_date_key) and ts_page < len(pages):
            tspot_date = _extract_zone_text(pages[ts_page], tx0, ty0, tx1, ty1)
            if tspot_date:
                fields[igra_date_key] = tspot_date
    finally:
        doc.close()

    return fields


def extract_raw_fields(pdf_path: str | Path) -> dict[str, str]:
    """
    Extract all form fields from a PDF.

    Tries AcroForm widget extraction first.  If the PDF is flattened (no
    widgets), falls back to coordinate-based text extraction calibrated for
    I-693 Edition 01/20/25.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary mapping field names to their values
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    fields = {}
    doc = fitz.open(str(pdf_path))

    try:
        for page in doc:
            for widget in page.widgets():
                if widget.field_name:
                    # Get field value, default to empty string
                    value = widget.field_value or ""
                    fields[widget.field_name] = value
    finally:
        doc.close()

    if not fields:
        # PDF is flattened — fall back to coordinate-based extraction
        print("DEBUG: No AcroForm fields found — using flattened PDF text extraction")
        fields = extract_fields_from_flattened_pdf(pdf_path)
        print(f"DEBUG: Flattened extraction found {len(fields)} fields")

    return fields


def extract_radio_button_selection(pdf_path: str | Path, field_prefix: str) -> tuple[int, str]:
    """
    Extract which radio button in a group is selected.
    
    For PDF radio button groups, all buttons share the same field_value (the export
    value of the selected button). To determine WHICH button is selected, we compare
    field_value to each button's on_state().
    
    Note: PyMuPDF may decode URL-encoded spaces in field_value but not in on_state,
    so we normalize both by replacing '#20' with spaces before comparison.
    
    Args:
        pdf_path: Path to the PDF file
        field_prefix: Common prefix for the radio button fields (e.g., 'Pt8Line1A4_SputumSmears')
        
    Returns:
        Tuple of (selected_index, on_state_value) or (-1, '') if none selected
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return (-1, '')
    
    doc = fitz.open(str(pdf_path))
    
    try:
        for page in doc:
            for widget in page.widgets():
                if widget.field_name and field_prefix in widget.field_name:
                    fv = widget.field_value or ""
                    os_val = widget.on_state() or ""
                    # Check if this button is selected (field_value == on_state)
                    # Normalize URL-encoded spaces (#20) for comparison
                    fv_norm = fv.replace("#20", " ")
                    os_norm = os_val.replace("#20", " ")
                    if fv and (fv == os_val or fv_norm == os_norm):
                        # Extract index from field name like "...SputumSmearsCultures[3]"
                        try:
                            idx_str = widget.field_name.split('[')[-1].rstrip(']')
                            idx = int(idx_str)
                            return (idx, widget.on_state())
                        except (ValueError, IndexError):
                            return (-1, widget.on_state())
    finally:
        doc.close()
    
    return (-1, '')


def extract_radio_button_selection_by_position(pdf_path: str | Path, field_prefix: str) -> tuple[int, str]:
    """
    Extract which radio button is selected, indexed by VISUAL POSITION (top-to-bottom).

    Unlike `extract_radio_button_selection` which returns the field-name index (which
    does not always match visual order), this function sorts widgets by their bounding
    box (rect.y0, then rect.x0) and returns the visual index of the selected button.

    This is robust against form revisions that reorder field-name indices but keep
    the visual layout the same.

    Returns:
        Tuple of (visual_index, on_state_value) or (-1, '') if none selected.
        visual_index 0 = topmost option, 1 = next, etc.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return (-1, '')

    doc = fitz.open(str(pdf_path))
    try:
        # Collect all widgets in the radio group along with their position.
        # IMPORTANT: extract field_value and on_state() eagerly here — PyMuPDF widget
        # objects are weakly referenced and become invalid once the page iterator
        # advances, so we must not store the widget object itself.
        group_widgets = []  # (y0, x0, field_value, on_state_value)
        for page in doc:
            for widget in page.widgets():
                if widget.field_name and field_prefix in widget.field_name:
                    rect = widget.rect
                    group_widgets.append((
                        rect.y0,
                        rect.x0,
                        widget.field_value or "",
                        widget.on_state() or "",
                    ))

        if not group_widgets:
            return (-1, '')

        # Sort by Y (top-to-bottom), then X (left-to-right) for tie-breaking
        group_widgets.sort(key=lambda t: (round(t[0], 1), round(t[1], 1)))

        # Find the selected widget (where field_value matches its on_state)
        for visual_idx, (_, _, fv, os_val) in enumerate(group_widgets):
            fv_norm = fv.replace("#20", " ")
            os_norm = os_val.replace("#20", " ")
            if fv and (fv == os_val or fv_norm == os_norm):
                return (visual_idx, os_val)
    finally:
        doc.close()

    return (-1, '')



def extract_sputum_results(pdf_path: str | Path) -> dict:
    """
    Extract sputum smear/culture results from I-693 PDF (Part 8.1.A(5)).
    
    The I-693 stores sputum data in these fields on page 7 (subform[6]):
      - Pt7Line1B1b_DateScreeningRun[0-11]: dates
        [0-2] = smear specimen dates (rows 1-3)
        [3-5] = smear result reported dates (rows 1-3)
        [6-8] = culture specimen dates (rows 1-3)
        [9-11] = culture result reported dates (rows 1-3)
      - Pt7Line1B1d_name[0-17]: result checkmarks ('X' = checked)
        [0-2] = smear Negative (rows 1-3)
        [3-5] = smear Positive (rows 1-3)
        [6-8] = culture Negative (rows 1-3)
        [9-11] = culture Positive M.TB (rows 1-3)
        [12-14] = culture Positive NTM (rows 1-3)
        [15-17] = culture Contaminated (rows 1-3)
    
    Returns:
        Dict with keys: smear_specimen_date_N, smear_result_date_N, smear_result_N,
                        culture_specimen_date_N, culture_result_date_N, culture_result_N
                        (N = 1, 2, 3)
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {}
    
    # Collect field values by index
    dates = {}  # index -> date value
    names = {}  # index -> name value
    
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[6]  # Page 7 (0-indexed)
        for widget in page.widgets():
            if not widget.field_name:
                continue
            val = widget.field_value or ""
            if "Pt7Line1B1b_DateScreeningRun" in widget.field_name:
                try:
                    idx = int(widget.field_name.split('[')[-1].rstrip(']'))
                    dates[idx] = val
                except (ValueError, IndexError):
                    pass
            elif "Pt7Line1B1d_name" in widget.field_name:
                try:
                    idx = int(widget.field_name.split('[')[-1].rstrip(']'))
                    names[idx] = val
                except (ValueError, IndexError):
                    pass
    finally:
        doc.close()
    
    result = {}
    
    # Smear dates: specimen=[0,1,2], result=[3,4,5]
    for row in range(3):
        n = row + 1
        result[f'smear_specimen_date_{n}'] = dates.get(row, '')
        result[f'smear_result_date_{n}'] = dates.get(row + 3, '')
        
        # Smear result: name[0-2]=Negative, name[3-5]=Positive
        neg = names.get(row, '').strip()
        pos = names.get(row + 3, '').strip()
        if pos:  # 'X' means checked
            result[f'smear_result_{n}'] = 'POS'
        elif neg:
            result[f'smear_result_{n}'] = 'NEG'
        else:
            result[f'smear_result_{n}'] = ''
    
    # Culture dates: specimen=[6,7,8], result=[9,10,11]
    for row in range(3):
        n = row + 1
        result[f'culture_specimen_date_{n}'] = dates.get(row + 6, '')
        result[f'culture_result_date_{n}'] = dates.get(row + 9, '')
        
        # Culture result: name[6-8]=Neg, [9-11]=Pos(M.TB), [12-14]=NTM, [15-17]=Contaminated
        neg = names.get(row + 6, '').strip()
        pos = names.get(row + 9, '').strip()
        ntm = names.get(row + 12, '').strip()
        contam = names.get(row + 15, '').strip()
        if pos:
            result[f'culture_result_{n}'] = 'POS'
        elif ntm:
            result[f'culture_result_{n}'] = 'NTM'
        elif contam:
            result[f'culture_result_{n}'] = 'CNTAMNTD'
        elif neg:
            result[f'culture_result_{n}'] = 'NEG'
        else:
            result[f'culture_result_{n}'] = ''
    
    print(f"DEBUG: Extracted sputum results: {result}")
    return result


def list_pdf_fields(pdf_path: str | Path) -> None:
    """
    Print all form fields in a PDF for debugging/discovery.
    
    Args:
        pdf_path: Path to the PDF file
    """
    fields = extract_raw_fields(pdf_path)
    print(f"\n{'='*60}")
    print(f"Form fields in: {pdf_path}")
    print(f"{'='*60}")
    
    for name, value in sorted(fields.items()):
        display_value = value[:50] + "..." if len(value) > 50 else value
        print(f"  {name}: '{display_value}'")
    
    print(f"\nTotal fields: {len(fields)}")


def _pdf_is_flattened(pdf_path: str | Path) -> bool:
    """Return True if the PDF has no AcroForm widgets (fully flattened)."""
    doc = fitz.open(str(Path(pdf_path)))
    try:
        for page in doc:
            for widget in page.widgets():
                if widget.field_name:
                    return False
    finally:
        doc.close()
    return True


def parse_date(value: str) -> date | None:
    """
    Parse a date string from various formats.
    
    Args:
        value: Date string from PDF
        
    Returns:
        date object or None if parsing fails
    """
    if not value:
        return None
    
    # Try common date formats
    formats = [
        "%m/%d/%Y",  # 01/15/2024
        "%m-%d-%Y",  # 01-15-2024
        "%Y-%m-%d",  # 2024-01-15
        "%d/%m/%Y",  # 15/01/2024 (EU format)
        "%B %d, %Y", # January 15, 2024
        "%b %d, %Y", # Jan 15, 2024
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    
    return None


def clean_a_number(value: str) -> str:
    """
    Clean A-Number to 9 digits.
    
    Args:
        value: Raw A-Number string (may have leading 'A' or spaces)
        
    Returns:
        9-digit A-Number string
    """
    if not value:
        return ""
    
    # Remove leading 'A' and any non-digit characters
    cleaned = "".join(c for c in value if c.isdigit())
    
    # Pad with leading zeros if needed
    return cleaned.zfill(9) if cleaned else ""


def set_nested_attr(obj: Any, path: str, value: Any) -> None:
    """
    Set a nested attribute using dot notation.
    
    Args:
        obj: Root object
        path: Dot-separated path like "applicant.family_name"
        value: Value to set
    """
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def extract_i693_data(pdf_path: str | Path) -> I693Form:
    """
    Extract I-693 form data from a PDF.
    
    Args:
        pdf_path: Path to the I-693 PDF
        
    Returns:
        Populated I693Form dataclass
    """
    pdf_path = Path(pdf_path)
    raw_fields = extract_raw_fields(pdf_path)
    
    form = I693Form(
        source_file=str(pdf_path),
        extraction_date=date.today(),
    )
    
    # Special handling for gender radio button (returns the selected value "M" or "F")
    # Both fields in the radio group return the same selected value
    male_field = "form1[0].#subform[0].Pt1Line3_Gender[0]"
    female_field = "form1[0].#subform[0].Pt1Line3_Gender[1]"
    
    # Check the actual value - radio buttons return "M" or "F" for the selected option
    gender_value = raw_fields.get(male_field, "") or raw_fields.get(female_field, "")
    if gender_value:
        gender_upper = gender_value.strip().upper()
        if gender_upper == "F" or "female" in gender_value.lower():
            form.applicant.sex = "F"
        elif gender_upper == "M" or "male" in gender_value.lower():
            form.applicant.sex = "M"
    
    for pdf_field, model_path in I693_FIELD_MAP.items():
        if pdf_field not in raw_fields:
            continue
        
        # Skip the gender field since we handled it specially above
        if "Gender" in pdf_field:
            continue
        
        raw_value = raw_fields[pdf_field]
        if not raw_value:
            continue
        
        try:
            # Determine value type and convert
            if "date" in model_path.lower():
                value = parse_date(raw_value)
            elif "a_number" in model_path:
                value = clean_a_number(raw_value)
            elif model_path.startswith("examination.has_") or model_path.endswith("_condition"):
                value = is_checkbox_checked(raw_value)
            else:
                value = raw_value.strip()
            
            if value is not None:
                set_nested_attr(form, model_path, value)
                
        except Exception as e:
            form.extraction_errors.append(f"Error parsing {pdf_field}: {e}")
    
    # === Part 1, Line 2: Apt./Ste./Flr. unit type + number ===
    # The three unit checkboxes cannot be read from the field map (they all
    # report the same value), so derive them here.
    unit_type = detect_unit_type(pdf_path, raw_fields)
    apt_raw = (form.applicant.apt_number or "").strip()
    # Drop stray checkbox export values that landed in the number field
    if apt_raw.lower() in ("yes", "on", "true", "off"):
        apt_raw = ""
    inline_type, apt_number = _split_unit_prefix(apt_raw)
    form.applicant.apt_number = apt_number
    form.applicant.unit_type = unit_type or inline_type
    print(
        f"DEBUG: Address unit - type='{form.applicant.unit_type}', "
        f"number='{form.applicant.apt_number}'"
    )
    if apt_number and not form.applicant.unit_type:
        print("DEBUG: Unit number present but no Apt./Ste./Flr. box detected")
    
    # Derive TB/IGRA test result from radio button group
    # These are radio buttons (not independent checkboxes): all buttons share the same
    # field_value, so we use on_state to reliably identify which is selected.
    # Verified on_state values: [0]='N' (Negative), [1]='P' (Positive), [2]='I' (Indeterminate)
    tb_result_idx, tb_result_on_state = extract_radio_button_selection(pdf_path, "Pt8Line1A1_Result")
    if tb_result_on_state == "N":
        form.examination.igra_test_result = "N"  # Negative
        form.examination.tb_skin_test_result = "N"
        print(f"DEBUG: TB/IGRA result: Negative (on_state='{tb_result_on_state}', index={tb_result_idx})")
    elif tb_result_on_state == "P":
        form.examination.igra_test_result = "P"  # Positive
        form.examination.tb_skin_test_result = "P"
        print(f"DEBUG: TB/IGRA result: Positive (on_state='{tb_result_on_state}', index={tb_result_idx})")
    elif tb_result_on_state == "I":
        form.examination.igra_test_result = "I"  # Indeterminate
        form.examination.tb_skin_test_result = "I"
        print(f"DEBUG: TB/IGRA result: Indeterminate (on_state='{tb_result_on_state}', index={tb_result_idx})")
    else:
        # Fallback: try the old checkbox approach for non-standard PDFs
        if form.examination.tb_result_positive and form.examination.tb_result_positive.lower() not in ("off", ""):
            form.examination.igra_test_result = "P"
            form.examination.tb_skin_test_result = "P"
            print(f"DEBUG: TB/IGRA result (fallback): Positive")
        elif form.examination.tb_result_negative and form.examination.tb_result_negative.lower() not in ("off", ""):
            form.examination.igra_test_result = "N"
            form.examination.tb_skin_test_result = "N"
            print(f"DEBUG: TB/IGRA result (fallback): Negative")
        elif form.examination.tb_result_indeterminate and form.examination.tb_result_indeterminate.lower() not in ("off", ""):
            form.examination.igra_test_result = "I"
            form.examination.tb_skin_test_result = "I"
            print(f"DEBUG: TB/IGRA result (fallback): Indeterminate")
    
    # Derive chest X-ray result from radio button group
    # These are radio buttons: widget.field_value is the SAME for all buttons in the group.
    # We use on_state to reliably identify which is selected.
    # Verified on_state values: [0]='N' (Normal), [1]='A' (Abnormal)
    xray_result_idx, xray_on_state = extract_radio_button_selection(pdf_path, "Pt8Line1A3_Results")
    if xray_on_state == "N":
        form.examination.chest_xray_result = "N"  # Normal
        print(f"DEBUG: X-ray result: Normal (on_state='{xray_on_state}', index={xray_result_idx})")
    elif xray_on_state == "A":
        form.examination.chest_xray_result = "A"  # Abnormal
        print(f"DEBUG: X-ray result: Abnormal (on_state='{xray_on_state}', index={xray_result_idx})")
    elif xray_on_state:  # Unknown on_state - try treating it as the value
        form.examination.chest_xray_result = xray_on_state
        print(f"DEBUG: X-ray result: '{xray_on_state}' (unexpected on_state, index={xray_result_idx})")
    else:
        # Fallback: try the old checkbox approach
        if is_checkbox_checked(form.examination.chest_xray_normal or ""):
            form.examination.chest_xray_result = "N"
        elif is_checkbox_checked(form.examination.chest_xray_abnormal or ""):
            form.examination.chest_xray_result = "A"
        print(f"DEBUG: X-ray result (fallback): '{form.examination.chest_xray_result}'")
    
    # Derive chest X-ray reason from radio button group (Part 8.1.A(2))
    # Detect by VISUAL POSITION (top-to-bottom), since field-name indices and on_state
    # values are not reliable across form editions.
    #
    # I-693 Edition 01/20/25 visual order:
    #   Position 0 → A: Chest X-ray not required (medically cleared for TB)
    #   Position 1 → B: Required due to initial screening test results
    #   Position 2 → C: Required due to TB signs/symptoms or immunosuppression (HIV)
    #   Position 3 → D: Required due to IGRA exception
    xray_reason_pos, xray_reason_on = extract_radio_button_selection_by_position(
        pdf_path, "Pt8Line1A2_InitialScreening"
    )
    position_to_letter = {0: "A", 1: "B", 2: "C", 3: "D"}
    reason_labels = {
        "A": "Not required (medically cleared)",
        "B": "Initial screening results",
        "C": "TB signs/symptoms or HIV",
        "D": "IGRA exception",
    }
    if xray_reason_pos in position_to_letter:
        letter = position_to_letter[xray_reason_pos]
        form.examination.initial_tb_screening = letter
        print(
            f"DEBUG: X-ray reason: {letter} - {reason_labels[letter]} "
            f"(visual_pos={xray_reason_pos}, on_state='{xray_reason_on}')"
        )
    else:
        # Fallback: default to A (not required)
        form.examination.initial_tb_screening = "A"
        print(
            f"DEBUG: X-ray reason: not detected "
            f"(visual_pos={xray_reason_pos}, on_state='{xray_reason_on}'), defaulting to A"
        )
    
    # Parse compound ID type field (Part 5.1)
    # The ID type field may contain a country suffix like "PASSPORT - PERU"
    # or "CONSULAR ID CARD - MEXICO". Split on " - " to extract:
    #   id_type (cleaned): "PASSPORT" or "CONSULAR ID CARD"
    #   id_issuing_country: "PERU" or "MEXICO"
    #   id_type_raw: original full string for the "Other" text field on Page 5
    raw_id_type = form.applicant.id_type or ""
    if raw_id_type:
        form.applicant.id_type_raw = raw_id_type.strip()
        # Split on dash with flexible spacing to separate ID type from country
        # Handles "PASSPORT - PERU", "PASSPORT- MEXICO", "PASSPORT -PERU", etc.
        import re
        dash_match = re.split(r'\s*[-–—]\s+|\s+[-–—]\s*', raw_id_type, maxsplit=1)
        if len(dash_match) == 2:
            form.applicant.id_type = dash_match[0].strip()
            form.applicant.id_issuing_country = dash_match[1].strip()
            print(f"DEBUG: Parsed compound ID type: '{raw_id_type}' -> type='{form.applicant.id_type}', country='{form.applicant.id_issuing_country}'")
        else:
            # Fallback: try splitting on dash between uppercase words with no spaces
            # e.g. "PASSPORT-MEXICO"
            fallback = re.match(r'^([A-Z\s\']+?)\s*-\s*([A-Z\s]+)$', raw_id_type.strip())
            if fallback:
                form.applicant.id_type = fallback.group(1).strip()
                form.applicant.id_issuing_country = fallback.group(2).strip()
                print(f"DEBUG: Parsed compound ID type (fallback): '{raw_id_type}' -> type='{form.applicant.id_type}', country='{form.applicant.id_issuing_country}'")
            else:
                # Check for known ID document types embedded in the string
                # e.g. "MEXICO CONSULAR ID CARD" -> type="CONSULAR ID CARD", country="MEXICO"
                known_id_types = [
                    "CONSULAR ID CARD",
                    "CONSULAR ID",
                    "PASSPORT",
                    "DRIVER'S LICENSE",
                    "DRIVERS LICENSE",
                    "STATE ID CARD",
                    "STATE ID",
                    "NATIONAL ID CARD",
                    "NATIONAL ID",
                    "MILITARY ID",
                ]
                cleaned = raw_id_type.strip().upper()
                matched_type = None
                for known in known_id_types:
                    if known in cleaned:
                        matched_type = known
                        break
                
                if matched_type:
                    # Extract country prefix (everything before the known type)
                    prefix = cleaned[:cleaned.index(matched_type)].strip()
                    form.applicant.id_type = matched_type
                    if prefix:
                        form.applicant.id_issuing_country = prefix
                        print(f"DEBUG: Parsed ID type by known pattern: '{raw_id_type}' -> type='{form.applicant.id_type}', country='{form.applicant.id_issuing_country}'")
                    else:
                        print(f"DEBUG: Matched known ID type (no country prefix): '{form.applicant.id_type}'")
                else:
                    form.applicant.id_type = raw_id_type.strip()
                    print(f"DEBUG: Simple ID type (no country suffix): '{form.applicant.id_type}'")
    
    # Derive sputum indicated status from checkbox fields (Part 8.1.A(4))
    # The I-693 has a radio group for sputum smears. The on_state EXPORT VALUES
    # represent the visual order on the form (not the field indices!):
    # - on_state 'No' = "No, not indicated"
    # - on_state 'B'  = "Yes, indicated due to signs or symptoms of TB"
    # - on_state 'C'  = "Yes, indicated due to chest X-ray suggestive of TB"
    # - on_state 'D'  = "Yes, indicated due to known HIV infection or extrapulmonary TB"
    # - on_state 'E'  = "Yes, indicated for end of treatment cultures"
    #
    # NOTE: The PDF field indices do NOT match the visual order!
    # Index [3] has on_state='E' (end treatment), Index [4] has on_state='D' (HIV)
    # So we must map based on ON_STATE VALUE, not index.
    
    sputum_selected_idx, sputum_on_state = extract_radio_button_selection(
        pdf_path, "Pt8Line1A4_SputumSmears"
    )
    
    print(f"DEBUG: Sputum radio group - selected index: {sputum_selected_idx}, on_state: {sputum_on_state}")
    
    # Map on_state value to indicated status and specific reason
    # This is the correct mapping based on export values, NOT indices
    SPUTUM_ON_STATE_MAP = {
        'No': ('NI', None),              # Not indicated
        'B': ('IND', 'signs_symptoms'),  # Signs/symptoms of TB
        'C': ('IND', 'chest_xray'),      # Chest X-ray suggestive of TB
        'D': ('IND', 'hiv_extrapulm'),   # Known HIV infection or extrapulmonary TB
        'E': ('IND', 'end_treatment'),   # End of treatment cultures
    }
    
    if sputum_on_state in SPUTUM_ON_STATE_MAP:
        status, reason = SPUTUM_ON_STATE_MAP[sputum_on_state]
        form.examination.sputum_indicated = status
        
        # Clear all reason fields, then set only the selected one
        form.examination.sputum_signs_symptoms = "Yes" if reason == 'signs_symptoms' else ""
        form.examination.sputum_chest_xray = "Yes" if reason == 'chest_xray' else ""
        form.examination.sputum_hiv_extrapulm = "Yes" if reason == 'hiv_extrapulm' else ""
        form.examination.sputum_end_treatment = "Yes" if reason == 'end_treatment' else ""
        
        print(f"DEBUG: Mapped on_state '{sputum_on_state}' to status='{status}', reason='{reason}'")
    elif sputum_selected_idx == -1:
        # Fallback: Could not determine from radio button extraction
        # Try the old logic based on field values
        sputum_values = [
            form.examination.sputum_not_indicated or "",
            form.examination.sputum_signs_symptoms or "",
            form.examination.sputum_chest_xray or "",
            form.examination.sputum_hiv_extrapulm or "",
            form.examination.sputum_end_treatment or "",
        ]
        non_empty_values = [v for v in sputum_values if v and v.strip() and v.lower() != "off"]
        if non_empty_values:
            # Check if index 0 is the only checked one
            if is_checkbox_checked(form.examination.sputum_not_indicated or ""):
                form.examination.sputum_indicated = "NI"
            else:
                form.examination.sputum_indicated = "IND"
    
    # === Extract Sputum Smear/Culture Results (Part 8.1.A(5)) ===
    # Uses known field names: Pt7Line1B1b_DateScreeningRun[0-11] for dates,
    # Pt7Line1B1d_name[0-17] for result checkmarks ('X' = checked)
    if form.examination.sputum_indicated == "IND":
        sputum_data = extract_sputum_results(pdf_path)
        if sputum_data:
            for key, value in sputum_data.items():
                if value:  # Only set non-empty values
                    setattr(form.examination, key, value)
            
            print(f"DEBUG: Sputum smear results: "
                  f"1={form.examination.smear_result_1}, "
                  f"2={form.examination.smear_result_2}, "
                  f"3={form.examination.smear_result_3}")
            print(f"DEBUG: Sputum smear dates: "
                  f"spec1={form.examination.smear_specimen_date_1}, "
                  f"res1={form.examination.smear_result_date_1}")
            print(f"DEBUG: Sputum culture results: "
                  f"1={form.examination.culture_result_1}, "
                  f"2={form.examination.culture_result_2}, "
                  f"3={form.examination.culture_result_3}")
            print(f"DEBUG: Sputum culture dates: "
                  f"spec1={form.examination.culture_specimen_date_1}, "
                  f"res1={form.examination.culture_result_date_1}")
        else:
            print("DEBUG: Sputum is indicated but no result fields found in PDF")
    
    # Derive TB Classification from radio button group (Part 8.1.A(6))
    # TBClassification[0-6] is a radio button group - all fields share the same field_value.
    #
    # IMPORTANT: PDF field indices do NOT follow visual layout order!
    # Verified actual on_state values from real I-693 PDFs:
    #   Index [0] on_state='NOClassA'               → No Class A or Class B TB
    #   Index [1] on_state='CA'                      → Class A Tuberculosis disease
    #   Index [2] on_state='B1Pul'                   → B1 TB, Pulmonary (NOT B0!)
    #   Index [3] on_state='B0'                      → B0 TB, Pulmonary (NOT B1!)
    #   Index [4] on_state='B1Extrapul'              → B1 TB, Extrapulmonary
    #   Index [5] on_state='B2#20TB#20Latent'        → B2 TB, LTBI Evaluation
    #   Index [6] on_state='Class#20B#20Other#20...' → Class B, Other Chest Condition (Non-TB)
    #
    # We use on_state values (not indices) to reliably identify the selected classification.

    # Map on_state export values → classification codes (most robust approach)
    ON_STATE_TO_CODE = {
        "NOClassA": "NO_TB",
        "CA": "CLASS_A",
        "B0": "B0_PULM",
        "B1Pul": "B1_PULM",
        "B1Extrapul": "B1_EXTRAPULM",
    }

    tb_class_idx, tb_class_on_state = extract_radio_button_selection(pdf_path, "Pt8Line1A6_TBClassification")

    if tb_class_on_state and tb_class_on_state in ON_STATE_TO_CODE:
        # Primary: match on descriptive on_state value (reliable)
        code = ON_STATE_TO_CODE[tb_class_on_state]
        form.examination.tb_classification = code
        print(f"DEBUG: TB classification: {code} (on_state='{tb_class_on_state}', index={tb_class_idx})")
    elif tb_class_on_state and "B2" in tb_class_on_state:
        # Handle URL-encoded on_state like 'B2#20TB#20Latent'
        form.examination.tb_classification = "B2_LTBI"
        print(f"DEBUG: TB classification: B2_LTBI (on_state='{tb_class_on_state}', index={tb_class_idx})")
    elif tb_class_on_state and ("Other" in tb_class_on_state or "Class#20B" in tb_class_on_state):
        # Handle URL-encoded on_state like 'Class#20B#20Other#20Chest#20'
        form.examination.tb_classification = "B_OTHER"
        print(f"DEBUG: TB classification: B_OTHER (on_state='{tb_class_on_state}', index={tb_class_idx})")
    else:
        # Fallback: try text-matching on the shared field_value for non-standard PDFs
        # All radio buttons share the same field_value (the export value of whichever is selected)
        tb_value = (form.examination.tb_class_no_tb or "").lower().strip()
        # Also try decoding URL-encoded values (e.g., 'B2#20TB#20Latent' → 'b2 tb latent')
        tb_value_decoded = tb_value.replace("#20", " ")
        TB_VALUE_MAP = {
            "noclassa": "NO_TB",
            "no tb": "NO_TB",
            "no class": "NO_TB",
            "class a": "CLASS_A",
            "b0": "B0_PULM",
            "b0 tb pulmonary": "B0_PULM",
            "b0 pulmonary": "B0_PULM",
            "b1pul": "B1_PULM",
            "b1 tb pulmonary": "B1_PULM",
            "b1 pulmonary": "B1_PULM",
            "b1extrapul": "B1_EXTRAPULM",
            "b1 tb extrapulmonary": "B1_EXTRAPULM",
            "b1 extrapulmonary": "B1_EXTRAPULM",
            "b2 tb latent": "B2_LTBI",
            "b2 ltbi": "B2_LTBI",
            "b2 tb": "B2_LTBI",
            "class b other": "B_OTHER",
            "b other": "B_OTHER",
            "other chest": "B_OTHER",
        }
        matched = False
        for check_value in (tb_value, tb_value_decoded):
            for key, code in TB_VALUE_MAP.items():
                if key in check_value:
                    form.examination.tb_classification = code
                    print(f"DEBUG: TB classification (fallback text match): {code} from value '{tb_value}'")
                    matched = True
                    break
            if matched:
                break
        if not matched and tb_value and tb_value != "off":
            print(f"DEBUG: Unknown TB classification value from PDF: '{tb_value}'")
    
    # === Flattened PDF: override Part 8 derivations from checkbox drawings ===
    # Every derivation above relies on AcroForm radio-button widgets, which do
    # not exist in a flattened PDF.  Re-derive Part 8 directly from the vector
    # checkbox marks and overlay the results.
    if _pdf_is_flattened(pdf_path):
        part8 = detect_part8_from_flattened_pdf(pdf_path)
        for attr, value in part8.items():
            setattr(form.examination, attr, value)
        print(f"DEBUG: Flattened Part 8 derivation: {part8}")

        # Part 8.1.A(5): smear/culture result tables are only filled in when
        # sputum smears and cultures were indicated.
        if form.examination.sputum_indicated == "IND":
            sputum_tables = extract_sputum_results_from_flattened_pdf(pdf_path)
            for attr, value in sputum_tables.items():
                setattr(form.examination, attr, value)

    return form


def validate_i693_form(form: I693Form) -> list[str]:
    """
    Validate extracted I-693 data for completeness.
    
    Args:
        form: Extracted I693Form
        
    Returns:
        List of validation warnings (empty if all required fields present)
    """
    warnings = []
    
    # Required applicant fields
    if not form.applicant.family_name:
        warnings.append("Missing: Family name")
    if not form.applicant.given_name:
        warnings.append("Missing: Given name")
    if not form.applicant.date_of_birth:
        warnings.append("Missing: Date of birth")
    
    # Important medical fields
    if not form.examination.exam_date:
        warnings.append("Missing: Examination date")
    
    # Civil surgeon info
    if not form.civil_surgeon.surgeon_name:
        warnings.append("Missing: Civil surgeon name")
    
    return warnings
