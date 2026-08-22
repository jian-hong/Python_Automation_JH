"""Polish lab report: Quire Sans 12, restore images from backup, SettlingTime 32-box grid.

Rebuilds carefully FROM BACKUP so drawings are not corrupt, then:
  - Intro: A = label, B:L merged; Circuitry >= 13 rows; Parameter/Sample Size styled
  - Precautions right-top; results tables moved under precautions (SettlingTime)
  - Photo grids: SettlingTime / SSSR / LSSR / NoPhaseReversal → 4 config bands × 8 boxes = 32
  - Single CH1/CH2 indicator (ORT style)
  - Workbook-wide Quire Sans 12
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sys
import zipfile
from copy import copy
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ate.reporting.golden_layout import (
    PHOTO_TITLE_BY_SHEET,
    TEST_SHEETS,
    apply_photo_grid_single,
    clear_error_placeholders,
    normalize_breaks,
    rows_for_wrap,
)
from ate.reporting.sheet_layout import (
    HEADER_BLUE,
    HEADER_BLUE_TEMPLATE,
    ORT_LAYOUT,
    YELLOW,
    _apply_border_range,
    _ensure_merge,
    _fill,
    apply_full_ort_layout,
    apply_standard_column_widths,
)

BACKUP = Path(r"C:\Users\OoiJianHong\Downloads\RS622XK_Lab_Report_TTSOP.backup.xlsx")
DB_LAB = Path(
    r"C:\Users\OoiJianHong\#Test_Database\OpAmp\RS622\TTSOP8\Version_1\workbook\RS622XK_Lab_Report_TTSOP.xlsx"
)
OUT_GOLDEN = Path(
    r"C:\Users\OoiJianHong\#Test_Database\OpAmp\RS622\TTSOP8\Version_1\workbook\RS622XK_Lab_Report_TTSOP_golden.xlsx"
)
DOWNLOADS = Path(r"C:\Users\OoiJianHong\Downloads\RS622XK_Lab_Report_TTSOP.xlsx")
MANIFEST = Path(
    r"C:\Users\OoiJianHong\#Test_Database\OpAmp\RS622\TTSOP8\Version_1\_manifest\polish_report.json"
)
FLOOR_MD = Path(
    r"C:\Users\OoiJianHong\#Test_Database\OpAmp\RS622\TTSOP8\Version_1\_manifest\OPERATOR_FLOOR_PLAN.md"
)

FONT_NAME = "Quire Sans"
FONT_SIZE = 12
SAMPLE_SIZE = 4

# Sheets that need 4 CL-config photo bands (32 boxes)
MULTI_CL_SHEETS = {
    "SettlingTime": ["CL = Open", "CL = 100pF", "CL = 330pF", "CL = 1nF"],
    "SSSR": ["CL = Open", "CL = 100pF", "CL = 330pF", "CL = 1nF"],
    "LSSR": ["CL = Open", "CL = 100pF", "CL = 330pF", "CL = 1nF"],
    "NoPhaseReversal": ["CL = Open", "CL = 100pF", "CL = 330pF", "CL = 1nF"],
}

_THIN = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_YELLOW = PatternFill("solid", fgColor=YELLOW)
_BLUE = PatternFill("solid", fgColor=HEADER_BLUE)
_BLUE_LBL = PatternFill("solid", fgColor=HEADER_BLUE_TEMPLATE)
_CH1 = PatternFill("solid", fgColor="FFFF00")
_CH2 = PatternFill("solid", fgColor="5B9BD5")


def qfont(bold: bool = False, color: str | None = None, size: int = FONT_SIZE) -> Font:
    kw: dict = {"name": FONT_NAME, "size": size, "bold": bold}
    if color:
        kw["color"] = color
    return Font(**kw)


def apply_font_tree(ws) -> int:
    """Force Quire Sans 12 on existing valued cells only (never invent CS* cells)."""
    n = 0
    for cell in list(getattr(ws, "_cells", {}).values()):
        if cell.value is None:
            continue
        try:
            prev = cell.font
            bold = bool(prev.bold) if prev else False
            color = None
            if prev and prev.color and prev.color.type == "rgb" and prev.color.rgb:
                rgb = prev.color.rgb
                if isinstance(rgb, str) and len(rgb) >= 6:
                    color = rgb[-6:] if len(rgb) == 8 or len(rgb) == 6 else None
                    if color and color.upper() in {"000000", "FF000000"}:
                        color = None
            cell.font = qfont(bold=bold, color=color)
            n += 1
        except Exception:
            pass
    return n


def style_label(cell) -> None:
    cell.fill = _BLUE_LBL
    cell.font = qfont(bold=True, color="FFFFFF")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def style_wrap(cell) -> None:
    cell.font = qfont()
    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)


def capture_sheet_images(ws) -> list[dict]:
    """Snapshot image file paths + approximate anchors before we clear sheet images."""
    out = []
    for img in list(getattr(ws, "_images", []) or []):
        path = getattr(img, "path", None) or getattr(img, "ref", None)
        anchor = getattr(img, "anchor", None)
        row = col = 1
        try:
            if hasattr(anchor, "_from"):
                row = int(anchor._from.row) + 1
                col = int(anchor._from.col) + 1
        except Exception:
            pass
        # openpyxl stores bytes in img._data()
        data = None
        try:
            data = img._data()
        except Exception:
            data = None
        out.append({"row": row, "col": col, "data": data, "width": img.width, "height": img.height})
    return out


def clear_sheet_images(ws) -> None:
    imgs = getattr(ws, "_images", None)
    if imgs is not None:
        imgs.clear()


def place_image_bytes(ws, data: bytes, *, anchor: str, max_w: int = 520, max_h: int = 280) -> None:
    if not data:
        return
    import io
    import tempfile

    tmp = Path(tempfile.gettempdir()) / f"_ate_img_{anchor}.png"
    tmp.write_bytes(data)
    img = XLImage(str(tmp))
    if img.width and img.width > max_w:
        scale = max_w / float(img.width)
        img.width = int(img.width * scale)
        img.height = int(img.height * scale)
    if img.height and img.height > max_h:
        scale = max_h / float(img.height)
        img.width = int(img.width * scale)
        img.height = int(img.height * scale)
    ws.add_image(img, anchor)


def merge_intro_stacked(ws, blocks: list[tuple[str, object, int, int]]) -> dict:
    """Rebuild left intro from row 1.

    blocks: list of (label, value, min_rows, max_rows)
    Column A = label merge; B:L = value merge. Returns end_row and ranges.
    """
    # Clear old left intro merges in A1:L40 (keep data values we pass in)
    for mr in list(ws.merged_cells.ranges):
        if mr.min_col <= 12 and mr.max_col <= 12 and mr.min_row <= 45:
            try:
                ws.unmerge_cells(str(mr))
            except Exception:
                pass

    # Write parameter + sample size header rows
    cursor = 1
    report = {}
    for label, value, min_r, max_r in blocks:
        # Clear target rows area lightly
        budget = rows_for_wrap(value, merge_cols=11, min_rows=min_r, max_rows=max_r)
        # Force circuitry minimum 13
        if label.lower() == "test circuitry":
            need = max(13, budget.rows)
        else:
            need = budget.rows
        end = cursor + need - 1
        for r in range(cursor, end + 1):
            for c in range(1, 13):
                try:
                    if not (r == cursor and c in (1, 2)):
                        ws.cell(r, c).value = None
                except AttributeError:
                    pass
        ws.cell(cursor, 1).value = label
        style_label(ws.cell(cursor, 1))
        ws.cell(cursor, 2).value = budget.text if budget.text else (None if value in (None, "") else value)
        style_wrap(ws.cell(cursor, 2))
        _ensure_merge(ws, f"A{cursor}:A{end}")
        _ensure_merge(ws, f"B{cursor}:L{end}")
        _apply_border_range(ws, cursor, end, 1, 12)
        for r in range(cursor, end + 1):
            ws.row_dimensions[r].height = 18
        report[label] = {"start": cursor, "end": end, "rows": need, "lines": budget.lines}
        cursor = end + 1
    return {"intro_end": cursor - 1, "blocks": report}


def read_intro_values(ws) -> dict[str, object]:
    found: dict[str, object] = {}
    for row in range(1, 50):
        lab = ws.cell(row, 1).value
        if not lab:
            continue
        key = str(lab).strip().lower()
        found[key] = ws.cell(row, 2).value
    # Fallbacks
    if "test parameter" not in found:
        found["test parameter"] = ws["B1"].value
    if "sample size" not in found:
        found["sample size"] = SAMPLE_SIZE
    return found


def ensure_precautions_right(ws) -> None:
    for mr in list(ws.merged_cells.ranges):
        if mr.min_col >= 14 and mr.max_col <= 17 and mr.min_row <= 5:
            try:
                ws.unmerge_cells(str(mr))
            except Exception:
                pass
    ws["N1"].value = "Precautions"
    style_label(ws["N1"])
    _ensure_merge(ws, "N1:Q1")
    _ensure_merge(ws, "N2:Q4")
    ws["N2"].font = qfont()
    ws["N2"].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    _apply_border_range(ws, 1, 4, 14, 17)


def place_single_ch_indicator(ws, start_row: int, start_col: int = 1) -> None:
    """One ORT-style CH1/CH2 indicator pair."""
    c1 = ws.cell(start_row, start_col)
    c2 = ws.cell(start_row + 1, start_col)
    c1.value = "CH1: IN+"
    c2.value = "CH2: VOUT"
    c1.fill = _CH1
    c2.fill = _CH2
    c1.font = qfont(bold=True)
    c2.font = qfont(bold=True)
    c1.alignment = Alignment(horizontal="center", vertical="center")
    c2.alignment = Alignment(horizontal="center", vertical="center")
    c1.border = _THIN
    c2.border = _THIN
    # Clear duplicate indicators nearby
    for r in range(max(1, start_row - 5), start_row + 15):
        for c in range(1, 8):
            if r in (start_row, start_row + 1) and c == start_col:
                continue
            v = ws.cell(r, c).value
            if v and ("CH1" in str(v) or "CH2" in str(v)):
                try:
                    ws.cell(r, c).value = None
                    ws.cell(r, c).fill = PatternFill()
                except Exception:
                    pass


def apply_photo_grid_32(
    ws,
    *,
    title: str,
    config_labels: list[str],
    start_row: int,
    body_rows: int = 10,
) -> dict:
    """4 config bands × 8 boxes (4 DUT × ChA/ChB) = 32 boxes; 1 empty row between bands."""
    anchors: dict = {}
    row = start_row
    for cfg_i, cfg in enumerate(config_labels, start=1):
        # Config banner across full width
        _ensure_merge(ws, f"A{row}:AF{row}")
        cell = ws.cell(row, 1)
        cell.value = f"{title} — {cfg}"
        cell.fill = _BLUE
        cell.font = qfont(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        row += 1
        band = apply_photo_grid_single(
            ws,
            title=f"{title} [{cfg}]",
            start_row=row,
            sample_size=SAMPLE_SIZE,
            body_rows=body_rows,
        )
        # Retitle unit headers to DUT #n only (cleaner)
        for i, start in enumerate((1, 9, 17, 25), start=1):
            h = ws.cell(row, start)
            h.value = f"{title} #{i}"
            h.font = qfont(bold=True, color="FFFFFF")
        for k, v in band.items():
            anchors[f"cfg{cfg_i}_{k}"] = v
        # body: header + channel + body_rows
        row = row + 2 + body_rows + 1  # +1 empty spacer row
    return {"start": start_row, "end": row - 2, "anchors": anchors}


def move_settling_results_right(ws, intro_end: int) -> int:
    """Build Settling Time result tables under precautions (right side).

    Returns the last row used on the right.
    """
    # Clear leftover left-side result titles if they sit just below intro
    # Keep numeric data by reading first
    # Simple structured ORT-like right block starting row 6
    start = 6
    # Average header
    _ensure_merge(ws, f"N{start}:U{start}")
    ws.cell(start, 14).value = "Settling Time (Average) - Channel A, Channel B"
    ws.cell(start, 14).fill = _YELLOW
    ws.cell(start, 14).font = qfont(bold=True)
    ws.cell(start, 14).alignment = Alignment(horizontal="center", vertical="center")

    ws.cell(start + 1, 14).value = "VS=±2.5V"
    ws.cell(start + 1, 14).font = qfont(bold=True)
    ws.cell(start + 1, 15).value = None  # average placeholder
    ws.cell(start + 1, 15).fill = PatternFill("solid", fgColor="92D050")
    ws.cell(start + 1, 15).font = qfont(bold=True)

    # Channel A / B tables
    def write_channel_block(top_row: int, left_col: int, name: str) -> None:
        _ensure_merge(
            ws,
            f"{get_column_letter(left_col)}{top_row}:{get_column_letter(left_col + 6)}{top_row}",
        )
        h = ws.cell(top_row, left_col)
        h.value = name
        h.fill = _YELLOW
        h.font = qfont(bold=True)
        h.alignment = Alignment(horizontal="center", vertical="center")

        headers = ["VS (V)", "Settling (ns)", "#1", "#2", "#3", "#4", "Average"]
        for i, text in enumerate(headers):
            c = ws.cell(top_row + 1, left_col + i)
            c.value = text
            c.fill = _BLUE
            c.font = qfont(bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _THIN
        # one data row scaffold
        ws.cell(top_row + 2, left_col).value = "±2.5V"
        ws.cell(top_row + 2, left_col).font = qfont()
        for i in range(7):
            ws.cell(top_row + 2, left_col + i).border = _THIN
            ws.cell(top_row + 2, left_col + i).alignment = Alignment(
                horizontal="center", vertical="center"
            )
            ws.cell(top_row + 2, left_col + i).font = qfont()
        # Average formula across #1..#4
        c1 = get_column_letter(left_col + 2)
        c4 = get_column_letter(left_col + 5)
        avg = ws.cell(top_row + 2, left_col + 6)
        avg.value = f"=IFERROR(AVERAGE({c1}{top_row+2}:{c4}{top_row+2}),\"\")"

    write_channel_block(start + 3, 14, "Channel A")  # N
    write_channel_block(start + 3, 23, "Channel B")  # W

    # Overshoot sub-table scaffold (4 CL rows) further down on right
    ov = start + 8
    _ensure_merge(ws, f"N{ov}:AD{ov}")
    ws.cell(ov, 14).value = "Overshoot (%) by CL — measure ChA then ChB, then CHANGE CL"
    ws.cell(ov, 14).fill = _YELLOW
    ws.cell(ov, 14).font = qfont(bold=True)
    ws.cell(ov, 14).alignment = Alignment(horizontal="center", vertical="center")

    def overshoot_block(top: int, left: int, name: str) -> None:
        _ensure_merge(ws, f"{get_column_letter(left)}{top}:{get_column_letter(left+6)}{top}")
        h = ws.cell(top, left)
        h.value = name
        h.fill = _YELLOW
        h.font = qfont(bold=True)
        h.alignment = Alignment(horizontal="center", vertical="center")
        headers = ["VS (V)", "Overshoot (%)", "#1", "#2", "#3", "#4", "Average"]
        for i, text in enumerate(headers):
            c = ws.cell(top + 1, left + i)
            c.value = text
            c.fill = _BLUE
            c.font = qfont(bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _THIN
        cls = ["CL = Open", "CL = 100pF", "CL = 330pF", "CL = 1nF"]
        for ri, cl in enumerate(cls):
            r = top + 2 + ri
            ws.cell(r, left).value = "±2.5V"
            ws.cell(r, left + 1).value = cl
            for i in range(7):
                cell = ws.cell(r, left + i)
                cell.border = _THIN
                cell.font = qfont()
                cell.alignment = Alignment(horizontal="center", vertical="center")
            c1 = get_column_letter(left + 2)
            c4 = get_column_letter(left + 5)
            ws.cell(r, left + 6).value = f"=IFERROR(AVERAGE({c1}{r}:{c4}{r}),\"\")"
        # merge VS column
        _ensure_merge(ws, f"{get_column_letter(left)}{top+2}:{get_column_letter(left)}{top+5}")

    overshoot_block(ov + 1, 14, "Channel A")
    overshoot_block(ov + 1, 23, "Channel B")
    return ov + 6


def polish_sheet(ws, name: str, saved_images: list[dict]) -> dict:
    info: dict = {"sheet": name}
    clear_error_placeholders(ws)
    apply_standard_column_widths(ws, ORT_LAYOUT, max_col=35)

    if name == "ORT":
        apply_full_ort_layout(ws, ORT_LAYOUT)
        ensure_precautions_right(ws)
        place_single_ch_indicator(ws, 41, 1)
        apply_font_tree(ws)
        info["mode"] = "ort"
        return info

    # Heavy rebuild ONLY for multi-CL sheets (results move right / 32 boxes).
    # Other sheets: preserve existing result tables; only fix intro spacing + fonts + indicator.
    if name not in MULTI_CL_SHEETS and name != "SettlingTime":
        from ate.reporting.golden_layout import hard_expand_intro_with_insert
        from ate.reporting.sheet_layout import ensure_sample_size

        ensure_sample_size(ws, SAMPLE_SIZE)
        ensure_precautions_right(ws)
        # Expand circuitry to >=13 if label exists
        for row in range(1, 40):
            lab = ws.cell(row, 1).value
            if lab and str(lab).strip().lower() == "test circuitry":
                hard_expand_intro_with_insert(ws, row, min_rows=13, max_rows=16)
                # Re-place first image into circuitry
                if saved_images:
                    clear_sheet_images(ws)
                    place_image_bytes(ws, saved_images[0]["data"], anchor=f"B{row}")
                    if len(saved_images) > 1:
                        # try datasheet row
                        for r2 in range(row, row + 30):
                            if ws.cell(r2, 1).value and "datasheet" in str(ws.cell(r2, 1).value).lower():
                                place_image_bytes(ws, saved_images[1]["data"], anchor=f"B{r2}", max_h=120)
                                break
                break
        # Single indicator near bottom of intro / before photos
        ind = None
        for row in range(1, 80):
            v = ws.cell(row, 1).value
            if v and "CH1" in str(v):
                ind = row
                break
        place_single_ch_indicator(ws, ind or 20, 1)
        apply_font_tree(ws)
        info["mode"] = "light_preserve"
        return info

    vals = read_intro_values(ws)
    param = vals.get("test parameter") or name
    sample = vals.get("sample size") or SAMPLE_SIZE
    cond = vals.get("test conditions") or ""
    circ = vals.get("test circuitry") or ""
    data = vals.get("datasheet") or ""
    conc = vals.get("test conclusion") or ""
    if isinstance(circ, str) and circ.strip().upper() in {"#VALUE!", "#REF!"}:
        circ = ""
    if isinstance(data, str) and data.strip().upper() in {"#VALUE!", "#REF!"}:
        data = ""

    clear_sheet_images(ws)

    blocks = [
        ("Test Parameter", param, 1, 2),
        ("Sample Size", sample, 1, 2),
        ("Test Conditions", cond, 4, 16),
        ("Test Circuitry", circ, 13, 16),
        ("Datasheet", data, 3, 6),
        ("Test Conclusion", conc, 3, 10),
    ]
    intro = merge_intro_stacked(ws, blocks)
    info["intro"] = intro
    ensure_precautions_right(ws)

    circuitry_start = intro["blocks"]["Test Circuitry"]["start"]
    if saved_images:
        place_image_bytes(
            ws,
            saved_images[0]["data"],
            anchor=f"B{circuitry_start}",
            max_w=520,
            max_h=260,
        )
    if len(saved_images) > 1:
        ds = intro["blocks"]["Datasheet"]["start"]
        place_image_bytes(ws, saved_images[1]["data"], anchor=f"B{ds}", max_w=520, max_h=120)

    intro_end = intro["intro_end"]
    place_single_ch_indicator(ws, intro_end + 1, 1)

    if name == "SettlingTime":
        right_end = move_settling_results_right(ws, intro_end)
        photo_start = max(right_end, intro_end) + 3
        grid = apply_photo_grid_32(
            ws,
            title="Settling Time",
            config_labels=MULTI_CL_SHEETS["SettlingTime"],
            start_row=photo_start,
            body_rows=10,
        )
        info["photo"] = grid
        info["mode"] = "settling_32"
    else:
        photo_start = intro_end + 4
        grid = apply_photo_grid_32(
            ws,
            title=PHOTO_TITLE_BY_SHEET.get(name, name),
            config_labels=MULTI_CL_SHEETS[name],
            start_row=photo_start,
            body_rows=10,
        )
        info["photo"] = grid
        info["mode"] = "multi_cl_32"

    apply_font_tree(ws)
    return info


def write_floor_plan() -> None:
    text = """# Operator floor plan — RS622 TTSOP8 Version_1

## Golden sheet zones (every test sheet)
1. **Left intro (A | B:L merged)** — Test Parameter, Sample Size (=4), Conditions, Circuitry (≥13 rows), Datasheet, Conclusion
2. **Right-top** — Precautions (N1:Q4), then result tables under it
3. **Indicator** — single `CH1: IN+` / `CH2: VOUT` (yellow/blue) like ORT
4. **Bottom photos** — merged boxes; paste screenshots from `#Test_Database\\...\\<Test>\\DUT_n\\screenshots`

## Font
- All cells: **Quire Sans 12**. Install Quire Sans on Windows if Excel falls back to Calibri.

## Wait / manual change map (automation pauses)

| Sheet | Fixture | Manual wait / change | Photo bands |
|-------|---------|----------------------|-------------|
| Slew Rate | BUFFER | Optional CL tweak (main knob CL); ChA then ChB | 8 (4 DUT × 2 ch) |
| GBW | G11 | Sweep frequency; wait settle each step | 8 |
| **SettlingTime** | BUFFER | **CHANGE CL** after ChA+ChB: Open → 100pF → 330pF → 1nF | **32 (4×8)** |
| **SSSR** | BUFFER | **CHANGE CL** each band (Open/100p/330p/1n) | **32** |
| **LSSR** | BUFFER | **CHANGE CL** each band | **32** |
| ORT | G_NEG100 | Change DUT; POS then NEG polarity | 16 (POS+NEG) |
| PSRR / CMRR / AOL | ATE | Supply / VCM sweeps — mostly automated later | 8 |
| EMIRR | ATE | RF inject setup | 8 |
| **NoPhaseReversal** | BUFFER | **CHANGE CL** each band; Vpp > source | **32** |
| VOS | G1001 | Change gain board / DUT | 8 |
| PowerOnTime | BUFFER | Power cycle timing | 8 |
| VOL / VOHL | ATE | Load conditions | 8 |
| Noise | ATE | Long integrate — wait | 8 |

## Settling Time specifically
1. Confirm BUFFER, RL=10kΩ, VS=±2.5V
2. For each CL in [Open, 100pF, 330pF, 1nF]:
   - Measure Channel A (#1..#4) → fill right table + paste 4 ChA boxes in that CL band
   - Measure Channel B (#1..#4) → fill + paste 4 ChB boxes
   - **STOP — change CL capacitor** — then next band
3. Overshoot (%) table on the right tracks the same 4 CL rows

## Image recovery
- Schematics re-embedded from backup into **Test Circuitry** / **Datasheet** boxes.
- If Excel still says “Repaired Records: Drawing…”, close file, reopen the `_golden.xlsx` copy, or re-paste PNGs from `#Test_Database`.
"""
    FLOOR_MD.write_text(text, encoding="utf-8")


def main() -> int:
    if not BACKUP.is_file():
        print(f"Missing backup: {BACKUP}")
        return 1

    # Start from pristine backup to restore drawings baseline
    src = BACKUP
    print(f"Source (backup): {src}")
    wb = load_workbook(src)

    # Capture images per sheet BEFORE polish
    images_by_sheet: dict[str, list] = {}
    for name in wb.sheetnames:
        images_by_sheet[name] = capture_sheet_images(wb[name])
        print(f"  images {name}: {len(images_by_sheet[name])}")

    report = {"generated": datetime.now().isoformat(timespec="seconds"), "sheets": {}}

    for name in TEST_SHEETS:
        if name not in wb.sheetnames:
            continue
        print(f"Polish: {name}")
        report["sheets"][name] = polish_sheet(wb[name], name, images_by_sheet.get(name, []))

    # Summary + Checklist fonts
    for name in ("Summary", "Checklist"):
        if name in wb.sheetnames:
            apply_font_tree(wb[name])

    write_floor_plan()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Floor plan: {FLOOR_MD}")
    print(f"Report: {MANIFEST}")

    saved = None
    for dest in (DB_LAB, OUT_GOLDEN, DOWNLOADS):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            wb.save(dest)
            saved = dest
            print(f"Saved: {dest}")
            break
        except PermissionError:
            print(f"Locked: {dest}")
    wb.close()
    if saved is None:
        return 2
    for dest in (DB_LAB, OUT_GOLDEN, DOWNLOADS):
        if dest == saved:
            continue
        try:
            shutil.copy2(saved, dest)
            print(f"Synced: {dest}")
        except Exception as exc:
            print(f"Sync skip {dest}: {exc}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
