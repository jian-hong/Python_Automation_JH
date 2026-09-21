"""Format check for adding a test / Logic DC SKU (live console, not a second system).

Run: python -m ate.core.check_add_test

Companion: python -m ate.core.check_logic_dc
           python -m ate.core.check_family_load
           python -m ate.core.check_test_detect
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_DOC = _REPO / "docs" / "LOGIC_DC.md"
_AGENTS = _REPO / "AGENTS.md"
_PLUGIN = _REPO / "docs" / "ATE_PLUGIN.md"
_LOGIC_DC = _REPO / "ate" / "tests" / "logic" / "logic_dc.py"


def check_add_test() -> list[str]:
    errors: list[str] = []
    if not _DOC.is_file():
        errors.append("docs/LOGIC_DC.md missing (how to add RS1Gxx by data)")
        return errors
    doc = _DOC.read_text(encoding="utf-8")
    for needle in (
        "STANDARD FORMAT",
        "Path A",
        "Path B",
        "Path C",
        "Detected tests",
        "Wrap + enable on part",
        "Test program",
        "logic_inputs",
        "threshold_isolation",
        "logic_dc",
        "dc.py",
        "test_params.yaml",
        "pass_mode",
        "fail-open",
        "enabled_tests",
        "unspec",
        "check_logic_dc",
        "check_family_load",
        "check_test_detect",
        "input_threshold",
        "icc",
    ):
        if needle not in doc:
            errors.append(f"LOGIC_DC.md must document {needle!r}")
    if "wizard" in doc.lower() and "do not" not in doc.lower():
        errors.append("LOGIC_DC.md must not introduce a wizard path")
    if "xyflow" in doc.lower() and "do not" not in doc.lower() and "not" not in doc.lower():
        errors.append("LOGIC_DC.md must not introduce xyflow")
    agents = _AGENTS.read_text(encoding="utf-8") if _AGENTS.is_file() else ""
    if "register(TestSpec" not in agents:
        errors.append("AGENTS.md must keep the Path A register(TestSpec) template")
    if "STANDARD FORMAT" not in agents or "Path A" not in agents:
        errors.append("AGENTS.md must name STANDARD FORMAT Path A/B/C")
    if "LOGIC_DC.md" not in agents:
        errors.append("AGENTS.md must point at docs/LOGIC_DC.md for Logic DC SKUs")
    plugin = _PLUGIN.read_text(encoding="utf-8") if _PLUGIN.is_file() else ""
    if "STANDARD FORMAT" not in plugin or "LOGIC_DC.md" not in plugin:
        errors.append("docs/ATE_PLUGIN.md must name STANDARD FORMAT and point at LOGIC_DC.md")
    src = _LOGIC_DC.read_text(encoding="utf-8")
    if "family_ingest" in src:
        errors.append("logic_dc.py must not import family_ingest")
    from ate.core.registry import all_tests, get, load_family
    from ate.tests.logic import logic_dc as ldc
    from ate.tests.logic.product_model import load_product_model, sim_icc_plan

    load_family("logic")
    ids = {t.id for t in all_tests()}
    for need in ("input_threshold", "icc", "delta_icc", "ii", "voh", "vol", "ioz"):
        if need not in ids:
            errors.append(f"logic family missing Path B id {need}")
    th = get("input_threshold")
    if th is None or th.run is not ldc._run_input_threshold:
        errors.append("input_threshold must stay logic_dc body (no per-chip fork)")
    from ate.tests.logic import dc as dcmod

    if dcmod._run_icc is not ldc._run_icc or dcmod._run_input_threshold is not ldc._run_input_threshold:
        errors.append("ate.tests.logic.dc must be the same runner as logic_dc (no per-chip fork)")
    dc_path = _REPO / "ate" / "tests" / "logic" / "dc.py"
    dc_src = dc_path.read_text(encoding="utf-8") if dc_path.is_file() else ""
    if "logic_dc" not in dc_src or "__getattr__" not in dc_src:
        errors.append("dc.py must re-export logic_dc (Product Model import name)")
    if "register(TestSpec" in dc_src:
        errors.append("dc.py must not register a second TestSpec suite")
    m08 = load_product_model("rs1g08")
    m97 = load_product_model("rs1g97")
    if m08 is None or sim_icc_plan(m08)["n"] != 4:
        errors.append("add-test SIM: 2-input AND must be 4 ICC corners")
    if m97 is None or sim_icc_plan(m97)["n"] != 8:
        errors.append("add-test SIM: 3-input RS1G97 must be 8 ICC corners")
    return errors


def main() -> int:
    errors = check_add_test()
    if errors:
        print("FAIL check_add_test:")
        for line in errors:
            print(f"  - {line}")
        return 1
    print(
        "OK check_add_test: Path A register + Path B product_model + Detect/Wrap "
        "documented; SIM 2-input=4 / 3-input=8 on shared DC ids. "
        "Also run: python -m ate.core.check_logic_dc && python -m ate.core.check_family_load"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
