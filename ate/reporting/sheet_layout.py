"""Standardized ORT-style lab-report sheet layout (RS622XK TTSOP)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# Template / user palette
HEADER_BLUE = "002060"
HEADER_BLUE_TEMPLATE = "0070C0"  # existing RS622 sheet labels
YELLOW = "FFFF00"
GREEN = "00B050"
GREEN_AVG = "92D050"  # existing average cell

DEFAULT_DATABASE_ROOT = Path(
    r"C:\Users\OoiJianHong\#Test_Database\OpAmp\RS622\TTSOP8\Version_1"
)


@dataclass
class PhotoBox:
    """One of 16 ORT photo cells."""

    key: str
    anchor: str
    unit: int
    polarity: str  # POS | NEG
    channel: str  # CHA | CHB


@dataclass
class LayoutSpec:
    """Shared geometry for ORT-style project introductory sheets."""

    sample_size: int = 4
    header_blue: str = HEADER_BLUE
    yellow: str = YELLOW
    green: str = GREEN

    # Intro (left column block)
    intro_label_col: int = 1  # A
    intro_value_col: int = 2  # B
    intro_value_end_col: int = 12  # L
    conditions_rows: tuple[int, int] = (3, 18)
    circuitry_rows: tuple[int, int] = (19, 32)
    datasheet_row: int = 33
    conclusion_rows: tuple[int, int] = (34, 39)

    # Right result block starts at column N
    right_col: int = 14

    # Bottom photo grid (Eugene ORT: 4 units × ChA/ChB, with 1-col gaps)
    photo_header_row_pos: int = 44
    photo_channel_row_pos: int = 45
    photo_body_rows_pos: tuple[int, int] = (46, 55)
    photo_header_row_neg: int = 57
    photo_channel_row_neg: int = 58
    photo_body_rows_neg: tuple[int, int] = (59, 68)
    photo_cols_per_box: int = 4
    # Top-left column (1-based) of each of 8 boxes: U1A,U1B,U2A,U2B,U3A,U3B,U4A,U4B
    # Matches template merges A46:D55, E46:H55, I46:L55, M46:P55, Q46:T55, U46:X55, Y46:AB55, AC46:AF55
    photo_box_start_cols: tuple[int, ...] = (1, 5, 9, 13, 17, 21, 25, 29)
    unit_header_start_cols: tuple[int, ...] = (1, 9, 17, 25)  # 8-col unit banners
    # Golden TTSOP rules: 16.00 width / 20.4 height
    standard_col_width: float = 16.0
    label_col_width: float = 16.0
    photo_row_height: float = 20.4


ORT_LAYOUT = LayoutSpec()

_THIN = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_NO_BORDER = Border()


def _fill(rgb: str) -> PatternFill:
    return PatternFill(start_color=rgb, end_color=rgb, fill_type="solid")


def _font_white_bold(size: int = 11) -> Font:
    return Font(bold=True, color="FFFFFF", size=size)


def _safe_unmerge(ws, coord: str) -> None:
    try:
        ws.unmerge_cells(coord)
    except (KeyError, ValueError):
        pass


def _ensure_merge(ws, coord: str) -> None:
    """Merge range if not already covered; skip if identical merge exists."""
    target = coord.upper()
    existing = {str(r).upper() for r in ws.merged_cells.ranges}
    if target in existing:
        return
    from openpyxl.utils import range_boundaries

    tmin_col, tmin_row, tmax_col, tmax_row = range_boundaries(target)
    for r in list(ws.merged_cells.ranges):
        omin_col, omin_row, omax_col, omax_row = range_boundaries(str(r))
        overlap = not (
            omax_col < tmin_col
            or omin_col > tmax_col
            or omax_row < tmin_row
            or omin_row > tmax_row
        )
        if overlap and str(r).upper() != target:
            _safe_unmerge(ws, str(r))
    if target not in {str(r).upper() for r in ws.merged_cells.ranges}:
        ws.merge_cells(target)


def _apply_border_range(ws, min_row: int, max_row: int, min_col: int, max_col: int) -> None:
    """Apply thin borders inside a bounded box only (never sheet-wide)."""
    # Guard against accidental huge ranges that inflate used area / Excel repair noise
    if max_row - min_row > 80 or max_col - min_col > 40:
        raise ValueError(
            f"Refusing oversized border range "
            f"R{min_row}:{max_row} C{min_col}:{max_col}"
        )
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            ws.cell(r, c).border = _THIN


def _clear_border_range(ws, min_row: int, max_row: int, min_col: int, max_col: int) -> None:
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            try:
                ws.cell(r, c).border = _NO_BORDER
            except AttributeError:
                pass


def ort_photo_boxes(spec: LayoutSpec | None = None) -> list[PhotoBox]:
    """Return 16 PhotoBox entries (DUT1..4 × POS/NEG × CHA/CHB)."""
    spec = spec or ORT_LAYOUT
    pos_row = spec.photo_body_rows_pos[0]
    neg_row = spec.photo_body_rows_neg[0]
    boxes: list[PhotoBox] = []
    for unit in range(1, 5):
        col_a = spec.photo_box_start_cols[(unit - 1) * 2]
        col_b = spec.photo_box_start_cols[(unit - 1) * 2 + 1]
        for polarity, row in (("POS", pos_row), ("NEG", neg_row)):
            for channel, col in (("CHA", col_a), ("CHB", col_b)):
                anchor = f"{get_column_letter(col)}{row}"
                key = f"DUT{unit}_{polarity}_{channel}"
                boxes.append(
                    PhotoBox(
                        key=key,
                        anchor=anchor,
                        unit=unit,
                        polarity=polarity,
                        channel=channel,
                    )
                )
    return boxes


def ort_photo_anchor_map(spec: LayoutSpec | None = None) -> dict[str, str]:
    """Return 16 photo-box top-left anchors for ORT sheet.

    Keys: ``pos_u{n}_chA``, ``pos_u{n}_chB``, ``neg_u{n}_chA``, ``neg_u{n}_chB``
    for unit n in 1..4.
    """
    out: dict[str, str] = {}
    for box in ort_photo_boxes(spec):
        ch = "chA" if box.channel == "CHA" else "chB"
        pol = "pos" if box.polarity == "POS" else "neg"
        out[f"{pol}_u{box.unit}_{ch}"] = box.anchor
    return out


def test_db_path(test_folder: str, root: Path | None = None) -> Path:
    """``#Test_Database\\...\\Version_1\\{test_folder}`` (created if missing)."""
    base = Path(root or DEFAULT_DATABASE_ROOT)
    dest = base / test_folder
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def apply_ort_photo_grid(ws, spec: LayoutSpec | None = None) -> dict[str, str]:
    """Ensure 16 photo boxes (2×8), unit/channel headers, borders; return anchors.

    Does not delete or move existing worksheet images (schematics stay put).
    """
    spec = spec or ORT_LAYOUT
    yellow = _fill(spec.yellow)
    blue = _fill(spec.header_blue)
    wrap_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Unit header row (Positive)
    for i, start in enumerate(spec.unit_header_start_cols, start=1):
        end = start + 7
        coord = f"{get_column_letter(start)}{spec.photo_header_row_pos}:{get_column_letter(end)}{spec.photo_header_row_pos}"
        _ensure_merge(ws, coord)
        cell = ws.cell(spec.photo_header_row_pos, start)
        cell.value = f"Positive Overload Recovery Time #{i}"
        cell.fill = blue
        cell.font = _font_white_bold()
        cell.alignment = wrap_center

    # Unit header row (Negative) — fix #4 typo if present as #1
    for i, start in enumerate(spec.unit_header_start_cols, start=1):
        end = start + 7
        coord = f"{get_column_letter(start)}{spec.photo_header_row_neg}:{get_column_letter(end)}{spec.photo_header_row_neg}"
        _ensure_merge(ws, coord)
        cell = ws.cell(spec.photo_header_row_neg, start)
        cell.value = f"Negative Overload Recovery Time #{i}"
        cell.fill = blue
        cell.font = _font_white_bold()
        cell.alignment = wrap_center

    # Channel A/B yellow headers + photo body merges
    channels = ("Channel A", "Channel B")
    for box_i, start_col in enumerate(spec.photo_box_start_cols):
        end_col = start_col + spec.photo_cols_per_box - 1
        ch_label = channels[box_i % 2]
        for ch_row, body in (
            (spec.photo_channel_row_pos, spec.photo_body_rows_pos),
            (spec.photo_channel_row_neg, spec.photo_body_rows_neg),
        ):
            ch_coord = (
                f"{get_column_letter(start_col)}{ch_row}:"
                f"{get_column_letter(end_col)}{ch_row}"
            )
            _ensure_merge(ws, ch_coord)
            c = ws.cell(ch_row, start_col)
            c.value = ch_label
            c.fill = yellow
            c.font = Font(bold=True)
            c.alignment = wrap_center

            body_coord = (
                f"{get_column_letter(start_col)}{body[0]}:"
                f"{get_column_letter(end_col)}{body[1]}"
            )
            # Clear leftover formulas / #VALUE! BEFORE merge (MergedCell is read-only)
            for r in range(body[0], body[1] + 1):
                for c in range(start_col, end_col + 1):
                    cell = ws.cell(r, c)
                    try:
                        cell.value = None
                    except AttributeError:
                        pass
                    cell.alignment = wrap_center
            _ensure_merge(ws, body_coord)
            _apply_border_range(ws, body[0], body[1], start_col, end_col)
            # Also border the channel header cell
            _apply_border_range(ws, ch_row, ch_row, start_col, end_col)

    # Row heights for photo block
    for r in range(spec.photo_header_row_pos, spec.photo_body_rows_neg[1] + 1):
        ws.row_dimensions[r].height = spec.photo_row_height

    return ort_photo_anchor_map(spec)


def ensure_sample_size(ws, sample_size: int = 4) -> None:
    """Set Sample Size value (typically B2) when the label is found in column A."""
    for row in range(1, 12):
        label = ws.cell(row, 1).value
        if label and str(label).strip().lower() == "sample size":
            ws.cell(row, 2).value = sample_size
            return
    # Fallback ORT / Slew convention
    if ws["A2"].value and "sample" in str(ws["A2"].value).lower():
        ws["B2"].value = sample_size


def standardize_intro_block(ws, spec: LayoutSpec | None = None) -> None:
    """Wrap-friendly merges for Test Conditions / Circuitry / Conclusion; sample size.

    Preserves existing schematic images; only adjusts cell merges/alignment/text fixes.
    """
    spec = spec or ORT_LAYOUT
    wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)
    label_font = Font(bold=True, color="FFFFFF")
    blue = _fill(HEADER_BLUE_TEMPLATE)  # match existing intro labels

    # Sample size
    ensure_sample_size(ws, spec.sample_size)

    # Fix ORT test-conditions voltage typo (±100V → ±100 mV)
    cond = ws.cell(spec.conditions_rows[0], spec.intro_value_col).value
    if isinstance(cond, str):
        fixed = cond.replace("IN- offset = ±100V", "IN- offset = ±100 mV")
        fixed = fixed.replace("IN- offset = ±100 V", "IN- offset = ±100 mV")
        fixed = fixed.replace("IN- offset = +/-100V", "IN- offset = ±100 mV")
        if fixed != cond:
            ws.cell(spec.conditions_rows[0], spec.intro_value_col).value = fixed

    # Tall merges for conditions / circuitry / conclusion (left intro)
    for label_row, (r0, r1), label in (
        (3, spec.conditions_rows, "Test Conditions"),
        (19, spec.circuitry_rows, "Test Circuitry"),
        (34, spec.conclusion_rows, "Test Conclusion"),
    ):
        # Label column tall merge
        lab_coord = f"A{r0}:A{r1}"
        _ensure_merge(ws, lab_coord)
        lab = ws.cell(r0, 1)
        if not lab.value:
            lab.value = label
        lab.fill = blue
        lab.font = label_font
        lab.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        val_coord = (
            f"{get_column_letter(spec.intro_value_col)}{r0}:"
            f"{get_column_letter(spec.intro_value_end_col)}{r1}"
        )
        _ensure_merge(ws, val_coord)
        val = ws.cell(r0, spec.intro_value_col)
        val.alignment = wrap

    # Datasheet label row
    ds = ws.cell(spec.datasheet_row, 1)
    if not ds.value:
        ds.value = "Datasheet"
    ds.fill = blue
    ds.font = label_font

    # Precautions header formatting (right top)
    prec = ws.cell(1, spec.right_col)
    if prec.value and "precaution" in str(prec.value).lower():
        prec.fill = blue
        prec.font = label_font
        prec.alignment = Alignment(horizontal="center", vertical="center")
        _ensure_merge(ws, f"N1:Q1")

    # Fix negative Channel B header if duplicated as Channel A
    # Positive: N10 / W10 ; Negative: N17 / W17
    for addr in ("W10", "W17"):
        cell = ws[addr]
        if cell.value and str(cell.value).strip() == "Channel A":
            cell.value = "Channel B"
    # Ensure Channel B negative header merge matches positive
    _ensure_merge(ws, "W17:AD17")
    if ws["W17"].value in (None, ""):
        ws["W17"].value = "Channel B"
    ws["W17"].fill = _fill(spec.yellow)
    ws["W17"].font = Font(bold=True)
    ws["W17"].alignment = Alignment(horizontal="center", vertical="center")


def apply_standard_column_widths(ws, spec: LayoutSpec | None = None, max_col: int = 35) -> None:
    """Consistent column widths across sheets (A slightly wider for labels)."""
    spec = spec or ORT_LAYOUT
    ws.column_dimensions["A"].width = spec.label_col_width
    for col in range(2, max_col + 1):
        ws.column_dimensions[get_column_letter(col)].width = spec.standard_col_width


def light_standardize_sheet(ws, sample_size: int = 4, spec: LayoutSpec | None = None) -> None:
    """Lighter pass for non-ORT sheets: sample size + standard column widths."""
    spec = spec or ORT_LAYOUT
    ensure_sample_size(ws, sample_size)
    apply_standard_column_widths(ws, spec)


def apply_full_ort_layout(ws, spec: LayoutSpec | None = None) -> dict[str, str]:
    """Apply intro + photo grid + column widths on the ORT sheet."""
    spec = spec or ORT_LAYOUT
    standardize_intro_block(ws, spec)
    anchors = apply_ort_photo_grid(ws, spec)
    apply_standard_column_widths(ws, spec)
    return anchors
