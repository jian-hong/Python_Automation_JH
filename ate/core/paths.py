"""Shared paths and constants for the modular ATE.

Canonical campaign paths resolve through ate.core.database.DbContext so the
operator can select Component / Part / Package / Version. Module-level
constants remain as defaults for the current RS622 TTSOP8 Version_1 campaign.
"""
from __future__ import annotations

from pathlib import Path

# Repo root (PythonAutomation/)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical characterization database root
TEST_DB_ROOT = Path(r"C:\Users\OoiJianHong\#Test_Database")

# Default campaign (overridden at runtime by DbContext)
PART_DB_ROOT = TEST_DB_ROOT / "OpAmp" / "RS622" / "TTSOP8" / "Version_1"
DB_WORKBOOK_DIR = PART_DB_ROOT / "workbook"
DB_MANIFEST_DIR = PART_DB_ROOT / "_manifest"
DB_SESSIONS_DIR = PART_DB_ROOT / "sessions"

# Primary lab report — editable copy inside Test Database workbook/
LAB_REPORT_PATH = DB_WORKBOOK_DIR / "RS622XK_Lab_Report_TTSOP.xlsx"

# Optional research workbook (legacy VOS Characterization)
RESEARCH_EXCEL_PATH = Path(r"C:\Users\OoiJianHong\Downloads\VOS Research.xlsx")

# Screenshots default into Test Database ORT folder; per-test helpers override
SCREENSHOT_DIR = PART_DB_ROOT / "ORT" / "screenshots"
CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
PARTS_DIR = CONFIG_DIR / "parts"

# LabAutomation_14.7 reference tree (recipes / registry patterns)
LAB_AUTOMATION_REF = Path(r"C:\Users\OoiJianHong\LabAutomation_14.7")

JSONRPC_HOST = "127.0.0.1"
# 8765 is AirGPT — do not reuse
JSONRPC_PORT = 8766


def active_root() -> Path:
    """Return the operator-selected campaign root (or default PART_DB_ROOT)."""
    try:
        from ate.core.database import get_context

        return get_context().root()
    except Exception:
        return PART_DB_ROOT


def test_folder(test_key: str) -> Path:
    """Return <Version>/ <TestKey> folder (e.g. ORT, VOS)."""
    try:
        from ate.core.database import get_context

        return get_context().test_folder(test_key)
    except Exception:
        return PART_DB_ROOT / test_key


def dut_folder(test_key: str, dut_index: int) -> Path:
    """Return <Version>/<TestKey>/DUT_N."""
    try:
        from ate.core.database import get_context

        return get_context().dut_folder(test_key, dut_index)
    except Exception:
        return test_folder(test_key) / f"DUT_{int(dut_index)}"


def screenshot_dir(test_key: str, dut_index: int | None = None) -> Path:
    """Per-DUT screenshots folder, or shared <Test>/screenshots if dut is None."""
    try:
        from ate.core.database import get_context

        return get_context().screenshot_dir(test_key, dut_index)
    except Exception:
        if dut_index is None:
            return test_folder(test_key) / "screenshots"
        return dut_folder(test_key, dut_index) / "screenshots"


def graph_dir(test_key: str, dut_index: int | None = None) -> Path:
    try:
        from ate.core.database import get_context

        return get_context().graph_dir(test_key, dut_index)
    except Exception:
        if dut_index is None:
            return test_folder(test_key) / "graphs"
        return dut_folder(test_key, dut_index) / "graphs"


def artifact_name(
    test_key: str,
    dut_index: int,
    variant: str,
    *,
    timestamp: str,
    ext: str = "jpg",
) -> str:
    """Standard name: ORT_1_POS_CHA_2026-07-22_094100.jpg"""
    return f"{test_key}_{int(dut_index)}_{variant}_{timestamp}.{ext.lstrip('.')}"


def sync_defaults_from_context() -> None:
    """Refresh module-level aliases after set_context (for legacy imports)."""
    global PART_DB_ROOT, DB_WORKBOOK_DIR, DB_MANIFEST_DIR, DB_SESSIONS_DIR
    global LAB_REPORT_PATH, SCREENSHOT_DIR
    from ate.core.database import get_context

    ctx = get_context()
    PART_DB_ROOT = ctx.root()
    DB_WORKBOOK_DIR = ctx.workbook_dir()
    DB_MANIFEST_DIR = ctx.manifest_dir()
    DB_SESSIONS_DIR = ctx.sessions_dir()
    LAB_REPORT_PATH = ctx.lab_report_path()
    SCREENSHOT_DIR = ctx.screenshot_dir("ORT")
