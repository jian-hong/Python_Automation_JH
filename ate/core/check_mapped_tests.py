"""Platform setup coverage: every sheet_map test has a real spec; DMM classifies.

Run: python -m ate.core.check_mapped_tests
"""
from __future__ import annotations

import sys

from ate.core.check_lab_report_sync import check_lab_report_sync
from ate.core.database import default_context, family_for_component, get_context
from ate.core.registry import all_tests, load_family
from ate.instruments.discovery import classify_idn
from ate.tests.opa.mapped_dc import CASES


def check_family_component_map() -> list[str]:
    errors: list[str] = []
    expect = {
        "Logic": "logic",
        "OpAmp": "opamp",
        "Lim": "switch",
        "AnalogSwitch": "switch",
        "Level": "level",
        "Power": "power",
    }
    for comp, fam in expect.items():
        got = family_for_component(comp)
        if got != fam:
            errors.append(f"family_for_component({comp!r}) -> {got!r} want {fam!r}")
    return errors


def check_dmm_classify() -> list[str]:
    errors: list[str] = []
    expect = {
        "RIGOL TECHNOLOGIES,MSO5072,X": "MSO",
        "RIGOL TECHNOLOGIES,DP832,X": "PSU",
        "RIGOL TECHNOLOGIES,DG811,X": "AWG",
        "KEITHLEY INSTRUMENTS,DMM6500,X": "DMM",
        "KEYSIGHT TECHNOLOGIES,34461A,X": "DMM",
        "AGILENT TECHNOLOGIES,34401A,X": "DMM",
        "KEITHLEY INSTRUMENTS INC.,MODEL 2000,X": "DMM",
        "SOMETHING ELSE": None,
    }
    for idn, kind in expect.items():
        got = classify_idn(idn)
        if got != kind:
            errors.append(f"classify_idn({idn!r}) -> {got!r} want {kind!r}")
    return errors


def check_mapped_ids() -> list[str]:
    load_family("opamp")
    ids = {t.id for t in all_tests()}
    missing = [c.test_id for c in CASES if c.test_id not in ids]
    if missing:
        return [f"mapped cases not registered: {missing}"]
    if "noise" not in ids:
        return ["noise TestSpec missing"]
    if any(c.test_id == "noise" for c in CASES):
        return ["noise must be the 0.1-10Hz body, not a mapped_dc screenshot stub"]
    vohl = next(t for t in all_tests() if t.id == "vohl")
    if "DMM" not in vohl.required_instruments:
        return ["vohl must require DMM"]
    return []


def check_map_folder_keys() -> list[str]:
    """Every sheet_map tests key has a spec whose lab_sheet matches excel_sheet."""
    import yaml

    load_family("opamp")
    ctx = default_context()
    path = ctx.sheet_map_path()
    if not path.is_file():
        return [f"sheet_map missing: {path}"]
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tests = data.get("tests") or {}
    sheets = {t.lab_sheet for t in all_tests() if t.lab_sheet}
    missing: list[str] = []
    for key, entry in tests.items():
        if not isinstance(entry, dict):
            continue
        sheet = entry.get("excel_sheet")
        if sheet and sheet not in sheets:
            missing.append(f"{key}->{sheet}")
    if missing:
        return ["sheet_map keys without spec: " + ", ".join(missing)]
    return []


def coverage_payload(mapping: dict | None = None) -> dict:
    """Setup-page snapshot: every sheet_map test vs registered lab_sheet.

    Uses the active DbContext so Logic campaigns report Logic coverage.
    """
    import yaml

    ctx = get_context()
    fam = family_for_component(ctx.component)
    if fam:
        load_family(fam)
    path = ctx.sheet_map_path()
    tests = {}
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tests = data.get("tests") or {}
    sheets = {t.lab_sheet: t.id for t in all_tests() if t.lab_sheet}
    # Logic: only count enabled part tests toward "missing"
    if fam in ("logic", "lim", "switch"):
        from ate.fixture.modes import enabled_tests_for_part

        default_pk = "rs2323" if fam in ("lim", "switch") else "rs29511"
        enabled = enabled_tests_for_part(
            str(ctx.part_key or default_pk),
            catalog=ctx.load_test_catalog(),
        )
        if enabled is not None:
            allow = set(enabled)
            sheets = {t.lab_sheet: t.id for t in all_tests() if t.lab_sheet and t.id in allow}
    missing: list[str] = []
    rows: list[dict] = []
    for key, entry in tests.items() if isinstance(tests, dict) else []:
        if not isinstance(entry, dict):
            continue
        sheet = entry.get("excel_sheet")
        spec_id = sheets.get(str(sheet)) if sheet else None
        if sheet and not spec_id:
            missing.append(f"{key}->{sheet}")
        rows.append(
            {
                "key": str(key),
                "excel_sheet": sheet,
                "test_id": spec_id,
                "folder": entry.get("folder"),
            }
        )
    mapping = mapping or {}
    return {
        "n_map": len(rows),
        "missing_specs": missing,
        "tests": rows,
        "dmm": "DMM" in mapping,
        "instruments": sorted(mapping.keys()),
        "sheet_map": str(path),
        "family": fam,
        "component": ctx.component,
        "part_key": ctx.part_key,
    }


def check_setup_dc_helper() -> list[str]:
    import generator_setup

    if not hasattr(generator_setup, "setup_dc"):
        return ["generator_setup.setup_dc missing (Logic DC / RS0204 / mapped_dc)"]
    return []


def check_mapped_tests() -> list[str]:
    return (
        check_family_component_map()
        + check_dmm_classify()
        + check_mapped_ids()
        + check_map_folder_keys()
        + check_lab_report_sync()
        + check_setup_dc_helper()
    )


def main() -> int:
    errors = check_mapped_tests()
    if errors:
        print("FAIL mapped-tests / DMM / lab-report:")
        for line in errors:
            print(f"  - {line}")
        return 1
    print("OK mapped-tests: every sheet_map test has a spec; DMM classifies; no stubs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
