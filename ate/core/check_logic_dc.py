"""Path B Logic DC: shared runner + product_model YAML (not per-chip forks).

Run: python -m ate.core.check_logic_dc
"""
from __future__ import annotations

import ast
import inspect
import re
import shutil
import sys
import tempfile
import textwrap
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ate.core.paths import PARTS_DIR
from ate.core.registry import all_tests, get, load_family
from ate.core.specs import infer_pass_mode, judge_value, load_part_specs
from ate.fixture.modes import enabled_tests_for_part
from ate.tests.logic.product_model import (
    CARD_FIELDS_SCHEMA_PATH,
    DATA_PATH_TEMPLATES,
    apply_dual_channel_continue,
    claimed_signed_without_datasheet,
    derive_isolation,
    dual_channel_continue,
    format_handoff_begin,
    has_product_model,
    isolation_for,
    isolation_for_run,
    is_datasheet_signed,
    is_open_drain,
    is_sequential,
    is_unconfirmed_status,
    iter_logic_corners,
    ioz_force_vector,
    known_pin_names,
    load_card_fields_schema,
    load_part_yaml,
    load_product_model,
    lookup_pass_mode,
    lookup_vcc_grid_limits,
    merge_recipe_channels,
    merge_vcc_grid,
    missing_data_path_keys,
    panel_save_keys,
    pins_named_in_wire_map,
    recipe_channels,
    sim_icc_plan,
    vcc_grid_owned,
    vcc_grid_stimulus,
    vcc_grid_unconfirmed,
    vectors_for_output,
    wire_map_for_test,
)

_LOGIC_DC = Path(__file__).resolve().parents[1] / "tests" / "logic" / "logic_dc.py"
_DC_ALIAS = Path(__file__).resolve().parents[1] / "tests" / "logic" / "dc.py"
_MODEL = Path(__file__).resolve().parents[1] / "tests" / "logic" / "product_model.py"
_THRESHOLD_SEARCH = Path(__file__).resolve().parents[1] / "tests" / "logic" / "threshold_search.py"
_OPERATOR_DOC = Path(__file__).resolve().parents[2] / "docs" / "LOGIC_DC_OPERATOR.md"

_PATH_B_IDS = (
    "input_threshold",
    "vth",
    "icc",
    "delta_icc",
    "ii",
    "voh",
    "vol",
    "ioz",
)


def _params(**kw):
    base = dict(vcc=5.0, part="", current_limit_a=0.05, pause_hook=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _no_part_name_ifs(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    errors: list[str] = []
    banned = {"rs1g97", "rs1g08", "rs1g126", "rs1g125"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for comp in node.comparators:
            if isinstance(comp, ast.Constant) and str(comp.value).strip().lower() in banned:
                errors.append(f"{path.name}: part-name compare around line {node.lineno}")
    if re.search(r"(?m)^\s*(?:import\s+Lim\b|from\s+Lim\b|import\s+Ariff\b|from\s+Ariff\b)", text):
        errors.append(f"{path.name}: must not import Lim.* / Ariff.*")
    if re.search(r"(?<![\"'\w])input\s*\(", text):
        errors.append(f"{path.name}: must not call input()")
    return errors


def _and_isolation_ok() -> list[str]:
    errors: list[str] = []
    m = load_product_model("rs1g08")
    if m is None:
        return ["rs1g08 product_model missing"]
    if m.has_oe() or m.schmitt:
        errors.append("rs1g08: oe must be none and schmitt false")
    if "ioz" in (enabled_tests_for_part("rs1g08") or []):
        errors.append("rs1g08 enabled_tests must not include ioz")
    derived = derive_isolation(
        logic_inputs=m.logic_inputs,
        truth_table=m.truth_table,
        output_pin=m.output_pin,
    )
    a = derived.get("A") or isolation_for(m, "A")
    b = derived.get("B") or isolation_for(m, "B")
    if not any(p.fix.get("B") == "H" and p.y_expect == "track" for p in a):
        errors.append(f"AND isolation A should track with B=H, got {a}")
    if not any(p.fix.get("A") == "H" and p.y_expect == "track" for p in b):
        errors.append(f"AND isolation B should track with A=H, got {b}")
    highs = vectors_for_output(m, "H")
    if not any(v.get("A") == "H" and v.get("B") == "H" for v in highs):
        errors.append("AND Y=H must include A=H B=H")
    if str(m.pass_mode.get("input_threshold") or "").lower() == "range":
        errors.append("rs1g08 must not collapse VIH/VIL into input_threshold: range")
    if lookup_pass_mode(m, "VIH_V", "input_threshold") != "min_only":
        errors.append("rs1g08 pass_mode VIH must be min_only")
    if lookup_pass_mode(m, "VIL_V", "input_threshold") != "max_only":
        errors.append("rs1g08 pass_mode VIL must be max_only")
    return errors


# Datasheet §4 FUNCTION TABLE rows (A B C -> Y). Not a signed confirm.
_RS1G97_SEC4 = (
    ("L", "L", "L", "L"),
    ("H", "L", "L", "L"),
    ("L", "H", "L", "H"),
    ("H", "H", "L", "H"),
    ("L", "L", "H", "L"),
    ("H", "L", "H", "H"),
    ("L", "H", "H", "L"),
    ("H", "H", "H", "H"),
)


def _row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (row.get("A", ""), row.get("B", ""), row.get("C", ""), row.get("Y", ""))


_CONFIRMED_VCC = [1.65, 2.3, 3.0, 4.5, 5.5]

# CONFIRMED Full load grid (same table 97/126). 100uA expanded onto vcc_list.
_SIGNED_VOH = (
    (1.65, -0.0001, 1.55),
    (2.3, -0.0001, 2.2),
    (3.0, -0.0001, 2.9),
    (4.5, -0.0001, 4.4),
    (5.5, -0.0001, 5.4),
    (1.65, -0.004, 1.2),
    (2.3, -0.008, 1.9),
    (3.0, -0.016, 2.4),
    (3.0, -0.024, 2.3),
    (4.5, -0.032, 3.8),
)
_SIGNED_VOL = (
    (1.65, 0.0001, 0.1),
    (2.3, 0.0001, 0.1),
    (3.0, 0.0001, 0.1),
    (4.5, 0.0001, 0.1),
    (5.5, 0.0001, 0.1),
    (1.65, 0.004, 0.45),
    (2.3, 0.008, 0.3),
    (3.0, 0.016, 0.4),
    (3.0, 0.024, 0.55),
    (4.5, 0.032, 0.55),
)

# RS1GT34 CONFIRMED card. 100uA expanded onto merged vcc_list. High-load named VCC only.
_RS1GT34_MERGED = [2.0, 3.3] + [round(4.5 + i * 0.1, 6) for i in range(11)]
_DRAFT_34_VOH = tuple(
    (v, -0.0001, round(v - 0.1, 6)) for v in _RS1GT34_MERGED
) + (
    (2.0, -0.008, 1.6),
    (3.3, -0.024, 2.5),
    (4.5, -0.032, 3.8),
    (5.0, -0.032, 4.2),
    (5.5, -0.032, 4.8),
)
_DRAFT_34_VOL = tuple((v, 0.0001, 0.1) for v in _RS1GT34_MERGED) + (
    (2.0, 0.008, 0.45),
    (3.3, 0.024, 0.55),
    (4.5, 0.032, 0.55),
    (5.0, 0.032, 0.5),
    (5.5, 0.032, 0.45),
)


def _table_sigs(rows: list, i_key: str, spec_key: str) -> set[tuple[float, float, float]]:
    out: set[tuple[float, float, float]] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            out.add(
                (
                    round(float(row["vcc"]), 6),
                    round(float(row[i_key]), 9),
                    round(float(row[spec_key]), 6),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _signed_voh_vol_ok(part: str) -> list[str]:
    errors: list[str] = []
    raw = load_part_yaml(part)
    voh = _table_sigs(raw.get("voh_table") if isinstance(raw.get("voh_table"), list) else [], "ioh_a", "spec_min")
    vol = _table_sigs(raw.get("vol_table") if isinstance(raw.get("vol_table"), list) else [], "iol_a", "spec_max")
    want_voh = {(round(a, 6), round(b, 9), round(c, 6)) for a, b, c in _SIGNED_VOH}
    want_vol = {(round(a, 6), round(b, 9), round(c, 6)) for a, b, c in _SIGNED_VOL}
    if voh != want_voh:
        errors.append(f"{part} voh_table must match CONFIRMED Full IOH grid (no extra/missing rows)")
    if vol != want_vol:
        errors.append(f"{part} vol_table must match CONFIRMED Full IOL grid (no extra/missing rows)")
    specs = {s.get("id"): s for s in load_part_specs(part)}
    for sid, _, spec in (
        ("VOH_4p5V_32mA", "min", 3.8),
        ("VOL_4p5V_32mA", "max", 0.55),
    ):
        row = specs.get(sid) or {}
        if sid.startswith("VOH"):
            if round(float(row.get("min") or 0), 6) != 3.8:
                errors.append(f"{part} limits missing {sid} min=3.8")
            mode = str(row.get("pass_mode") or "").replace("_", "-")
            if mode not in ("min-only", "min"):
                errors.append(f"{part} {sid} pass_mode must be min-only")
        else:
            if round(float(row.get("max") or 0), 6) != 0.55:
                errors.append(f"{part} limits missing {sid} max=0.55")
            mode = str(row.get("pass_mode") or "").replace("_", "-")
            if mode not in ("max-only", "max"):
                errors.append(f"{part} {sid} pass_mode must be max-only")
    pm = raw.get("product_model") if isinstance(raw.get("product_model"), dict) else {}
    dc = pm.get("dc_limits") if isinstance(pm.get("dc_limits"), dict) else {}
    for which in ("voh", "vol"):
        st = str((dc.get(which) or {}).get("status") or "") if isinstance(dc.get(which), dict) else ""
        if st.upper() == "PROVISIONAL":
            errors.append(f"{part} dc_limits.{which} must drop PROVISIONAL once the load grid is wired")
    recipe = pm.get("recipe") if isinstance(pm.get("recipe"), dict) else {}
    try:
        if abs(float(recipe.get("settle_s")) - 0.05) > 1e-9:
            errors.append(f"{part} recipe.settle_s must be 0.05 (DC Spec), got {recipe.get('settle_s')}")
        if int(recipe.get("stable_n")) != 3:
            errors.append(f"{part} recipe.stable_n must be 3")
        if abs(float(recipe.get("stable_eps_V")) - 0.005) > 1e-9:
            errors.append(f"{part} recipe.stable_eps_V must be 0.005")
        if abs(float(recipe.get("settle_timeout_s")) - 2.0) > 1e-9:
            errors.append(f"{part} recipe.settle_timeout_s must be 2.0")
        if "stable_eps_A" not in recipe:
            errors.append(
                f"{part} recipe.stable_eps_A must be present and null "
                "(do not invent a uA default)"
            )
        else:
            raw_a = recipe.get("stable_eps_A")
            if raw_a is not None and str(raw_a).strip().lower() not in ("", "null", "none", "~"):
                errors.append(
                    f"{part} recipe.stable_eps_A must stay null "
                    "(do not invent a uA default; ground via panel / test_params overlay)"
                )
    except (TypeError, ValueError):
        errors.append(f"{part} recipe settle loop keys missing")
    return errors


def _fail_closed_until_signed(part: str, m) -> list[str]:
    """UNCONFIRMED / signed-looking tokens fail-close until Datasheet-signed CONFIRMED."""
    errors: list[str] = []
    if claimed_signed_without_datasheet(m.truth_table_status):
        errors.append(
            f"{part} truth_table.status={m.truth_table_status!r} must not claim confirm "
            "without Datasheet-signed"
        )
    if claimed_signed_without_datasheet(m.isolation_status):
        errors.append(
            f"{part} isolation.status={m.isolation_status!r} must not claim confirm "
            "without Datasheet-signed"
        )
    if claimed_signed_without_datasheet(m.status):
        errors.append(
            f"{part} product_model.status={m.status!r} must not claim confirm "
            "without Datasheet-signed"
        )
    if (
        is_datasheet_signed(m.truth_table_status)
        and is_datasheet_signed(m.isolation_status)
        and is_datasheet_signed(m.status or m.truth_table_status)
    ):
        return errors
    errors.append(
        f"{part} truth_table.status={m.truth_table_status} isolation.status={m.isolation_status} "
        "UNCONFIRMED (not Datasheet-signed CONFIRMED; not greenable)"
    )
    return errors


def _status_tokens_ok() -> list[str]:
    """from_datasheet_function_table is not Datasheet-signed and is not greenable."""
    errors: list[str] = []
    bogus = "from_datasheet_function_table"
    if is_datasheet_signed(bogus):
        errors.append("from_datasheet_function_table must not be treated as Datasheet-signed")
    if not is_unconfirmed_status(bogus):
        errors.append("from_datasheet_function_table must fail-close as UNCONFIRMED (not greenable)")
    if not claimed_signed_without_datasheet(bogus):
        errors.append("from_datasheet_function_table must not look signed/confirmed")
    if not is_datasheet_signed("CONFIRMED"):
        errors.append("CONFIRMED must pass the Datasheet-signed CONFIRMED status gate")
    if claimed_signed_without_datasheet("CONFIRMED") or is_unconfirmed_status("CONFIRMED"):
        errors.append("CONFIRMED must not fail-close as unsigned / UNCONFIRMED")
    if is_datasheet_signed("CONFIRM"):
        errors.append("bare CONFIRM (no ED) must not pass the Datasheet-signed gate")
    return errors


def _rs1g97_holds() -> list[str]:
    """Data holds for RS1G97. Status gate passes on Datasheet-signed CONFIRMED.

    Isolation is checked against derive_isolation(truth_table). C-track
    A:H B:L is CONFIRMED (not PROPOSED HOLD CONFIRM).
    """
    errors: list[str] = []
    m = load_product_model("rs1g97")
    if m is None:
        return ["rs1g97 product_model missing"]
    if m.has_oe():
        errors.append("rs1g97 oe must be none")
    if not m.schmitt:
        errors.append("rs1g97 schmitt must be true (VT+/VT-)")
    en = set(enabled_tests_for_part("rs1g97") or [])
    for banned in ("ioz", "ioff", "ioff_leakage", "off_current"):
        if banned in en:
            errors.append(f"rs1g97 must not enable {banned}")
    for need in ("input_threshold", "icc", "delta_icc", "ii", "voh", "vol"):
        if need not in en:
            errors.append(f"rs1g97 enabled_tests missing {need}")
    pins = {p.name: p.number for p in m.pins}
    want_pins = {"A": 3, "B": 1, "C": 6, "Y": 4, "GND": 2, "VCC": 5}
    for name, num in want_pins.items():
        if pins.get(name) != num:
            errors.append(f"rs1g97 pin {name} must be number {num} (datasheet §7), got {pins.get(name)}")
    got_rows = {_row_key(r) for r in m.truth_table}
    want_rows = set(_RS1G97_SEC4)
    if got_rows != want_rows:
        errors.append(
            f"rs1g97 truth_table must be Datasheet §4 rows only (got {sorted(got_rows)})"
        )
    derived = derive_isolation(
        logic_inputs=m.logic_inputs,
        truth_table=m.truth_table,
        output_pin=m.output_pin,
    )
    a = derived.get("A") or []
    b = derived.get("B") or []
    c = derived.get("C") or []
    if not any(p.fix.get("B") == "L" and p.fix.get("C") == "H" and p.y_expect == "track" for p in a):
        errors.append("rs1g97 isolation from table: A with B:L C:H must track")
    if not any(p.fix.get("B") == "H" and p.fix.get("C") == "H" and p.y_expect == "track" for p in a):
        errors.append("rs1g97 isolation from table: A with B:H C:H must track")
    if not any(p.fix.get("A") == "L" and p.fix.get("C") == "L" and p.y_expect == "track" for p in b):
        errors.append("rs1g97 isolation from table: B with A:L C:L must track")
    if not any(p.fix.get("A") == "H" and p.fix.get("B") == "L" and p.y_expect == "track" for p in c):
        errors.append("rs1g97 isolation from table: C with A:H B:L must track")
    if not any(p.fix.get("A") == "L" and p.fix.get("B") == "H" and p.y_expect == "invert" for p in c):
        errors.append("rs1g97 isolation from table: C with A:L B:H must invert")
    yaml_a = isolation_for(m, "A")
    if yaml_a:
        yaml_sigs = {(tuple(sorted(p.fix.items())), p.y_expect) for p in yaml_a}
        der_sigs = {(tuple(sorted(p.fix.items())), p.y_expect) for p in a}
        if not yaml_sigs.issubset(der_sigs):
            errors.append("rs1g97 YAML isolation must match derive_isolation(truth_table)")
    yaml_c = isolation_for(m, "C")
    track_c = [
        p
        for p in yaml_c
        if p.fix.get("A") == "H" and p.fix.get("B") == "L" and p.y_expect == "track"
    ]
    if not track_c:
        errors.append("rs1g97 C-track A:H B:L must exist (CONFIRMED)")
    elif any(
        "PROPOSED" in str(p.status or "").upper() or "HOLD CONFIRM" in str(p.status or "").upper()
        for p in track_c
    ):
        errors.append("rs1g97 C-track A:H B:L must not stay PROPOSED HOLD CONFIRM")
    invert_c = [
        p
        for p in yaml_c
        if p.fix.get("A") == "L" and p.fix.get("B") == "H" and p.y_expect == "invert"
    ]
    if not invert_c:
        errors.append("rs1g97 C invert A:L B:H must stay")
    c_run = isolation_for_run(m, "C")
    if not c_run or c_run[0].y_expect != "track":
        errors.append("rs1g97 run isolation C must use CONFIRMED track A:H B:L")
    elif c_run[0].fix.get("A") != "H" or c_run[0].fix.get("B") != "L":
        errors.append(f"rs1g97 run isolation C track hold must be A:H B:L, got {c_run[0].fix}")
    a_run = isolation_for_run(m, "A")
    if not a_run or a_run[0].y_expect != "track":
        errors.append("rs1g97 run isolation A must prefer first track")
    c_drive = m.pin_drive.get("C")
    if c_drive is None or c_drive.src != "psu" or c_drive.ch != 3:
        errors.append("rs1g97 pin_drive C must be PSU CH3 (CH2 is Y-load/vref)")
    errors += _fail_closed_until_signed("rs1g97", m)
    if lookup_pass_mode(m, "VTPLUS_V", "input_threshold") != "range":
        errors.append("rs1g97 pass_mode VT+ must be range")
    if lookup_pass_mode(m, "VTMINUS_V", "input_threshold") != "range":
        errors.append("rs1g97 pass_mode VT- must be range")
    if lookup_pass_mode(m, "HYST", "input_threshold") != "range":
        errors.append("rs1g97 pass_mode HYST must be range")
    if str(m.pass_mode.get("input_threshold") or "").lower() == "range" and "VT+" not in m.pass_mode and "vth_vt_plus" not in m.pass_mode:
        errors.append("rs1g97 must not collapse VT+/VT- into a single input_threshold: range")
    got_vcc = [round(float(x), 6) for x in m.vcc_list]
    if got_vcc != _CONFIRMED_VCC:
        errors.append(f"rs1g97 vcc_list must be CONFIRMED {_CONFIRMED_VCC}, got {m.vcc_list}")
    errors += _signed_voh_vol_ok("rs1g97")
    if lookup_pass_mode(m, "VOH", "voh") != "min_only":
        errors.append("rs1g97 pass_mode VOH must be min_only")
    if lookup_pass_mode(m, "VOL", "vol") != "max_only":
        errors.append("rs1g97 pass_mode VOL must be max_only")
    specs = {s.get("id"): s for s in load_part_specs("rs1g97")}
    if specs.get("ICC_uA", {}).get("test") != "icc":
        errors.append("rs1g97 ICC_uA spec test must be icc (Path B id)")
    icc_mode = str(specs.get("ICC_uA", {}).get("pass_mode") or "").replace("_", "-")
    if icc_mode and icc_mode not in ("max-only", "max"):
        errors.append("rs1g97 ICC_uA pass_mode must be max-only when present")
    vt_mode = str(specs.get("VTPLUS_V", {}).get("pass_mode") or "")
    if vt_mode and vt_mode.replace("_", "-") != "range":
        errors.append("rs1g97 VTPLUS_V pass_mode must be range when present")
    src = _LOGIC_DC.read_text(encoding="utf-8")
    if "INSTRUMENT_SENSE ICC: DMM-on-VCC" not in src:
        errors.append("logic_dc.py must document INSTRUMENT_SENSE ICC: DMM-on-VCC")
    if "INSTRUMENT_SENSE VOH:" not in src or "INSTRUMENT_SENSE IOZ:" not in src:
        errors.append("logic_dc.py must document VOH/VOL/IOZ force/sense")
    if "SETTLE: measure-after-settle" not in src or "_wait_settled_voltage" not in src:
        errors.append("logic_dc.py must settle then measure (VOH/VOL/threshold)")
    if "_mux97_isolation_ok" in src or "_mux97_isolation_ok" in _MODEL.read_text(encoding="utf-8"):
        errors.append("_mux97_isolation_ok must not remain as a green gate")
    return errors


def _buf126_ok() -> list[str]:
    errors: list[str] = []
    m = load_product_model("rs1g126")
    if m is None:
        return ["rs1g126 product_model missing"]
    if not m.has_oe() or m.oe_mode != "high":
        errors.append("rs1g126 oe must be active high")
    en = set(enabled_tests_for_part("rs1g126") or [])
    if "ioz" not in en:
        errors.append("rs1g126 enabled_tests must include ioz")
    for ac in ("ten", "tdis"):
        if ac not in en:
            errors.append(f"rs1g126 must keep AC id {ac}")
    if "ioff_leakage" in en:
        errors.append("rs1g126 Path B DC uses ioz not ioff_leakage")
    a = isolation_for(m, "A")
    if not a:
        errors.append("rs1g126 isolation A missing (leave configurable, do not drop)")
    else:
        if any(p.fix.get("OE") != "H" for p in a):
            errors.append("rs1g126 A isolation must hold OE active; do not invent unused data ties")
    run_a = isolation_for_run(m, "A")
    if not run_a or run_a[0].y_expect != "track":
        errors.append("rs1g126 run isolation A must track while OE active")
    if str(m.pass_mode.get("input_threshold") or "").lower() == "range":
        errors.append("rs1g126 must not collapse VIH/VIL into input_threshold: range")
    if lookup_pass_mode(m, "VIH_V", "input_threshold") != "min_only":
        errors.append("rs1g126 pass_mode VIH must be min_only")
    if lookup_pass_mode(m, "VIL_V", "input_threshold") != "max_only":
        errors.append("rs1g126 pass_mode VIL must be max_only")
    raw = load_part_yaml("rs1g126")
    pm = raw.get("product_model") if isinstance(raw.get("product_model"), dict) else {}
    tt = pm.get("truth_table") if isinstance(pm.get("truth_table"), dict) else {}
    iso = pm.get("isolation") if isinstance(pm.get("isolation"), dict) else {}
    for label, st in (
        ("truth_table.status", (tt or {}).get("status")),
        ("isolation.status", (iso or {}).get("status")),
        ("truth_table_status", pm.get("truth_table_status")),
        ("isolation_status", pm.get("isolation_status")),
    ):
        token = str(st or "").strip().lower().replace("_", "-")
        if "from-datasheet" in token:
            errors.append(f"rs1g126 {label}={st!r} must not look signed (use UNCONFIRMED or CONFIRMED)")
    got_vcc = [round(float(x), 6) for x in m.vcc_list]
    if got_vcc != _CONFIRMED_VCC:
        errors.append(f"rs1g126 vcc_list must be CONFIRMED {_CONFIRMED_VCC}, got {m.vcc_list}")
    errors += _signed_voh_vol_ok("rs1g126")
    if lookup_pass_mode(m, "VOH", "voh") != "min_only":
        errors.append("rs1g126 pass_mode VOH must be min_only")
    if lookup_pass_mode(m, "VOL", "vol") != "max_only":
        errors.append("rs1g126 pass_mode VOL must be max_only")
    errors += _fail_closed_until_signed("rs1g126", m)
    return errors


def _fn_src(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            chunk = ast.get_source_segment(src, node)
            if chunk:
                return chunk
    return ""


def _settle_loop_ok() -> list[str]:
    """Timeout must FAIL (not last-reading pass). ICC/force must settle-to-stable."""
    errors: list[str] = []
    src = _LOGIC_DC.read_text(encoding="utf-8")
    if "time.sleep(_settle" in src:
        errors.append("logic_dc must not sleep(_settle) only; settle-to-stable + hard timeout")
    if re.search(r"return sum\(window\) / len\(window\) if window else", src):
        errors.append("_wait_settled must not soft-return last reading on timeout")
    if "settle timeout" not in src:
        errors.append("logic_dc settle timeout must raise RuntimeError / FAIL")
    wait_src = _fn_src(src, "_wait_settled")
    volt_src = _fn_src(src, "_wait_settled_voltage")
    if not wait_src or not volt_src:
        errors.append("logic_dc must define _wait_settled and _wait_settled_voltage")
    if wait_src:
        if "while True" in wait_src:
            errors.append("_wait_settled must not hang forever (no unbounded while True)")
        if "raise RuntimeError" not in wait_src:
            errors.append("_wait_settled timeout must raise RuntimeError")
        if re.search(r"if \(time\.monotonic\(\) - t0\) >= timeout:\s+return ", wait_src):
            errors.append("_wait_settled must not return last reading when timeout expires")
        if "stable_eps_A" not in wait_src:
            errors.append("_wait_settled current must use stable_eps_A only")
        if "stable_eps_V" not in wait_src:
            errors.append("_wait_settled voltage must keep stable_eps_V")
        if "NON_TIGHT" not in wait_src:
            errors.append("_wait_settled current must offer NON_TIGHT when stable_eps_A is null")
        if "FAIL-closed" not in wait_src and "stable_eps_A missing" not in wait_src:
            errors.append("tight current settle must FAIL-closed when stable_eps_A is null/missing")
        if re.search(r"kind == \"current\".*_recipe_num\(\s*model,\s*[\"']stable_eps_V\"", wait_src):
            errors.append("_wait_settled current must not reuse stable_eps_V as amps")
    power_src = _fn_src(src, "_power_vcc")
    if "time.sleep" in power_src:
        errors.append("_power_vcc must not sleep-as-settle; caller uses settle-to-stable")
    for name in ("_run_icc", "_run_delta_icc", "_run_ii", "_run_ioz"):
        body = _fn_src(src, name)
        if not body:
            errors.append(f"logic_dc {name} missing")
            continue
        if "_wait_settled_current_ua" not in body and "_wait_settled(" not in body:
            errors.append(f"{name} must settle-to-stable (current) after VCC/force, not sleep then avg")
        if "_avg_current_ua" in body:
            errors.append(f"{name} must not measure current via _avg_current_ua after sleep-only")
        if "_power_vcc" in body and "_wait_settled_current_ua" not in body:
            errors.append(f"{name} must wait settled after _power_vcc")
        if name == "_run_icc" and body.count("_wait_settled_current_ua") < 2:
            errors.append("_run_icc must wait settled after VCC and after each _apply_levels")
        if name == "_run_delta_icc" and body.count("_wait_settled_current_ua") < 3:
            errors.append("_run_delta_icc must wait settled after VCC, _apply_levels, and pin force")
    voh_src = _fn_src(src, "_run_voh_path_b")
    vol_src = _fn_src(src, "_run_vol_path_b")
    if "_wait_settled_voltage" not in voh_src or "_wait_settled_voltage" not in vol_src:
        errors.append("VOH/VOL must keep settled voltage (min_only/max_only; no invented loads)")
    from ate.tests.logic import logic_dc as ldc

    m = load_product_model("rs1g97")
    if m is None:
        errors.append("rs1g97 product_model missing for settle SIM")
        return errors
    fast = replace(
        m,
        recipe={
            **dict(m.recipe),
            "settle_s": 0.0,
            "stable_n": 3,
            "stable_eps_V": 0.001,
            "settle_timeout_s": 0.05,
        },
    )

    class _FlatDmm:
        def query(self, *_a, **_k):
            return "1.234"

        def write(self, *_a, **_k):
            return None

    class _RampDmm:
        def __init__(self) -> None:
            self.n = 0

        def query(self, *_a, **_k):
            self.n += 1
            return str(self.n * 0.1)

        def write(self, *_a, **_k):
            return None

    try:
        got = ldc._wait_settled_voltage(_FlatDmm(), fast, setup=False)
        if abs(float(got) - 1.234) > 1e-9:
            errors.append(f"settled voltage SIM must return the stable mean, got {got!r}")
    except Exception as exc:
        errors.append(f"settled voltage SIM raised on stable DMM: {exc!r}")
    try:
        ldc._wait_settled_voltage(_RampDmm(), fast, setup=False)
        errors.append("settle timeout must raise RuntimeError / FAIL (not return last reading)")
    except RuntimeError as exc:
        if "settle timeout" not in str(exc).lower() and "not stable" not in str(exc).lower():
            errors.append(f"settle timeout error must name timeout/not stable, got {exc!r}")
    except Exception as exc:
        errors.append(f"settle timeout must be RuntimeError, got {exc!r}")

    class _FlatCurr:
        def query(self, *_a, **_k):
            return "1e-6"

        def write(self, *_a, **_k):
            return None

    try:
        i_ua = ldc._wait_settled_current_ua(_FlatCurr(), fast, setup=False)
        if abs(float(i_ua) - 1.0) > 1e-6:
            errors.append(f"NON_TIGHT current SIM must return uA after settle_s, got {i_ua!r}")
        if ldc._current_settle_tag(fast) != "NON_TIGHT":
            errors.append("null stable_eps_A must tag settle=NON_TIGHT (not greenable as tight-settle)")
    except RuntimeError as exc:
        errors.append(
            f"honest current path with null stable_eps_A must not raise; got {exc!r}"
        )
    except Exception as exc:
        errors.append(f"NON_TIGHT current SIM raised: {exc!r}")
    try:
        ldc._wait_settled(_FlatCurr(), fast, kind="current", setup=False, tight=True)
        errors.append("tight current settle without stable_eps_A must FAIL-closed")
    except RuntimeError as exc:
        msg = str(exc)
        if "stable_eps_A" not in msg:
            errors.append(f"tight current settle null eps must name stable_eps_A, got {exc!r}")
        if "FAIL-closed" not in msg and "tight" not in msg.lower():
            errors.append(f"tight current settle must say FAIL-closed/tight, got {exc!r}")
    except Exception as exc:
        errors.append(f"tight current settle without stable_eps_A must be RuntimeError, got {exc!r}")
    try:
        ramp_i = ldc._wait_settled_current_ua(_RampDmm(), fast, setup=False)
        if abs(float(ramp_i) - 1e5) > 1.0:
            errors.append(
                f"NON_TIGHT must measure once (RampDmm first=0.1A -> 1e5 uA), got {ramp_i!r}"
            )
    except RuntimeError as exc:
        errors.append(f"NON_TIGHT must not timeout-FAIL, got {exc!r}")
    except Exception as exc:
        errors.append(f"NON_TIGHT ramp SIM raised: {exc!r}")
    grounded = replace(
        fast,
        recipe={**dict(fast.recipe), "stable_eps_A": 1.0},  # SIM probe window, not a SKU uA default
    )
    try:
        i_ua = ldc._wait_settled_current_ua(_FlatCurr(), grounded, setup=False)
        if abs(float(i_ua) - 1.0) > 1e-6:
            errors.append(f"settled current SIM must return uA when stable_eps_A is set, got {i_ua!r}")
    except Exception as exc:
        errors.append(f"settled current SIM raised with grounded stable_eps_A: {exc!r}")
    over = load_product_model("rs1g97", overlay={"stable_eps_A": 1.0})
    if over is None or over.recipe.get("stable_eps_A") != 1.0:
        errors.append("test_params overlay must set stable_eps_A")
    bare = load_product_model("rs1g97")
    if bare is not None and bare.recipe.get("stable_eps_A") not in (None,):
        errors.append("rs1g97 recipe.stable_eps_A must stay null without overlay")
    tagged = ldc._finish(
        fast,
        "icc",
        {
            "summary": "ICC SIM",
            "data": {"rows": [{"ICC_uA": 1.0}]},
            "measurements": [{"id": "ICC_uA", "value": 1.0}],
        },
    )
    if (tagged.get("data") or {}).get("settle") != "NON_TIGHT":
        errors.append("ICC result must tag settle=NON_TIGHT when stable_eps_A is null")
    if (tagged.get("data") or {}).get("tight_settle_greenable") is not False:
        errors.append("NON_TIGHT ICC must not be greenable as tight-settle")
    return errors


def _rs1gt34_ok() -> list[str]:
    """RS1GT34 Path B CONFIRMED (Jian Hong 2026-09-18). Copy attached card. No invent.

    ICCT 500uA @5.5 one_in@3.4 maps to delta_icc -- not delta_offset_v=0.6.
    No IOZ. Search: limit-scaled first step, on-hit skip, no reverse.
    Dual Excel: auto overwrite Version; pretty never auto.
    """
    errors: list[str] = []
    m = load_product_model("rs1gt34")
    if m is None:
        return ["rs1gt34 product_model missing (Path B CONFIRMED)"]
    yaml = load_part_yaml("rs1gt34")
    if str(yaml.get("package") or "") != "SOT23-5":
        errors.append(f"rs1gt34 package must be SOT23-5, got {yaml.get('package')!r}")
    if int(yaml.get("sample_size") or 0) != 1:
        errors.append(f"rs1gt34 sample_size must be 1, got {yaml.get('sample_size')}")
    if m.sample_size != 1:
        errors.append(f"rs1gt34 product_model sample_size must be 1, got {m.sample_size}")
    if m.schmitt:
        errors.append("rs1gt34 schmitt must be false (not Schmitt; VIH/VIL)")
    if m.has_oe():
        errors.append("rs1gt34 oe must be none")
    if list(m.logic_inputs) != ["A"]:
        errors.append(f"rs1gt34 logic_inputs must be [A], got {m.logic_inputs}")
    if m.output_pin != "Y":
        errors.append("rs1gt34 output_pin must be Y")
    en = set(enabled_tests_for_part("rs1gt34") or [])
    for banned in ("ioz", "ioff", "ioff_leakage", "off_current"):
        if banned in en:
            errors.append(f"rs1gt34 must not enable {banned} (Ioff is not IOZ)")
    for need in ("input_threshold", "icc", "ii", "voh", "vol", "delta_icc"):
        if need not in en:
            errors.append(f"rs1gt34 enabled_tests missing {need}")
    fx = yaml.get("fixture_modes") if isinstance(yaml.get("fixture_modes"), dict) else {}
    logic_fx = fx.get("LOGIC") if isinstance(fx.get("LOGIC"), dict) else {}
    fx_tests = {str(x) for x in (logic_fx.get("tests") or [])}
    if "delta_icc" not in en or "delta_icc" not in fx_tests:
        errors.append("rs1gt34 must enable delta_icc (ICCT mapped 500uA @5.5 one_in@3.4)")
    pins = {p.name: (p.number, p.role) for p in m.pins}
    want_pins = {"NC": (1, "nc"), "A": (2, "input"), "GND": (3, "gnd"), "Y": (4, "output"), "VCC": (5, "vcc")}
    for name, (num, role) in want_pins.items():
        got = pins.get(name)
        if got is None or got[0] != num or got[1] != role:
            errors.append(f"rs1gt34 pin {name} must be number {num} role {role}, got {got}")
    got_rows = {tuple(sorted((k, v) for k, v in r.items())) for r in m.truth_table}
    want_rows = {tuple(sorted({"A": "L", "Y": "L"}.items())), tuple(sorted({"A": "H", "Y": "H"}.items()))}
    if got_rows != want_rows:
        errors.append(f"rs1gt34 truth_table must be Y=A (A L->L / H->H), got {m.truth_table}")
    if round(float(m.vcc_op_min or 0), 6) != 2.0 or round(float(m.vcc_op_max or 0), 6) != 5.5:
        errors.append(f"rs1gt34 VCC op must be 2.0-5.5, got {m.vcc_op_min}..{m.vcc_op_max}")
    if vcc_grid_stimulus(m) != "PSU_MSO":
        errors.append(f"rs1gt34 stimulus must be PSU_MSO, got {vcc_grid_stimulus(m)}")
    grid = m.vcc_grid or {}
    if not is_datasheet_signed(grid.get("status")):
        errors.append(f"rs1gt34 vcc_grid.status must be CONFIRMED, got {grid.get('status')}")
    if vcc_grid_unconfirmed(m):
        errors.append("rs1gt34 vcc_grid must be Datasheet-signed CONFIRMED")
    for st_name, st in (
        ("status", m.status),
        ("truth_table", m.truth_table_status),
        ("isolation", m.isolation_status),
    ):
        if not is_datasheet_signed(st):
            errors.append(f"rs1gt34 {st_name}={st!r} must be CONFIRMED (Jian Hong 2026-09-18)")
    errors += _fail_closed_until_signed("rs1gt34", m)
    fixed = grid.get("fixed_points") or []
    fixed_v = sorted(round(float(p.get("vcc")), 6) for p in fixed if isinstance(p, dict) and p.get("vcc") is not None)
    if fixed_v != [2.0, 3.3]:
        errors.append(f"rs1gt34 fixed_points vcc must be [2.0, 3.3], got {fixed_v}")
    if any(round(float(p.get("vcc")), 6) == 4.5 for p in fixed if isinstance(p, dict)):
        errors.append("rs1gt34 4.5 must be a range step, not a fixed-point row")
    want_fixed = {
        2.0: (1.0, 0.3),
        3.3: (1.5, 0.55),
    }
    for pt in fixed:
        if not isinstance(pt, dict):
            continue
        v = round(float(pt.get("vcc")), 6)
        if v not in want_fixed:
            continue
        vih, vil = want_fixed[v]
        if round(float(pt.get("VIH_min_V")), 6) != vih or round(float(pt.get("VIL_max_V")), 6) != vil:
            errors.append(f"rs1gt34 fixed {v} VIH/VIL must be {vih}/{vil}, got {pt}")
    bands = grid.get("ranges") or []
    if len(bands) != 1:
        errors.append(f"rs1gt34 must have one range 4.5-5.5 step 0.1, got {bands}")
    else:
        band = bands[0]
        if (
            round(float(band.get("start")), 6) != 4.5
            or round(float(band.get("stop")), 6) != 5.5
            or round(float(band.get("step")), 6) != 0.1
            or round(float(band.get("VIH_min_V")), 6) != 2.0
            or round(float(band.get("VIL_max_V")), 6) != 0.8
        ):
            errors.append(f"rs1gt34 range must be 4.5-5.5 step 0.1 VIH>=2.0 VIL<=0.8, got {band}")
    merged = [round(float(x), 6) for x in merge_vcc_grid(grid)]
    want_merged = list(_RS1GT34_MERGED)
    if merged != want_merged:
        errors.append(f"rs1gt34 merged vcc_list must be {want_merged}, got {merged}")
    got_vcc = [round(float(x), 6) for x in m.vcc_list]
    if got_vcc != want_merged:
        errors.append(f"rs1gt34 model.vcc_list must be merged grid, got {m.vcc_list}")
    lim50 = lookup_vcc_grid_limits(m, 5.0) or {}
    if lim50.get("source") != "range":
        errors.append(f"rs1gt34 VCC=5.0 must own the range band, got {lim50}")
    if round(float(lim50.get("VIH_min_V") or 0), 6) != 2.0 or round(float(lim50.get("VIL_max_V") or 0), 6) != 0.8:
        errors.append(f"rs1gt34 VCC=5.0 limits must be VIH>=2.0 VIL<=0.8, got {lim50}")
    lim20 = lookup_vcc_grid_limits(m, 2.0) or {}
    if lim20.get("source") != "fixed":
        errors.append(f"rs1gt34 VCC=2.0 must own the fixed point, got {lim20}")
    owned = vcc_grid_owned(grid)
    if owned.get(4.5, {}).get("source") != "range":
        errors.append("rs1gt34 4.5 must inherit range-band limits (not a fixed-point row)")
    a_drive = m.pin_drive.get("A")
    if a_drive is None or a_drive.src != "psu" or a_drive.ch != 3:
        errors.append("rs1gt34 pin_drive A must be PSU CH3 (PSU_MSO; do not steal AWG CH1)")
    wm = m.wire_map if isinstance(m.wire_map, dict) else {}
    psu = wm.get("psu") if isinstance(wm.get("psu"), dict) else {}
    ch2 = psu.get("CH2") if isinstance(psu.get("CH2"), dict) else {}
    if (
        str(ch2.get("pin") or "") != "Y"
        or str(ch2.get("use") or "") != "load"
        or int(ch2.get("number") or 0) != 4
    ):
        errors.append(
            "rs1gt34 wire_map.psu.CH2 must be pin Y number 4 use=load "
            "(Path B VOH/VOL fixture; not a new net)"
        )
    tests_wm = wm.get("tests") if isinstance(wm.get("tests"), dict) else {}
    if "delta_icc" not in tests_wm:
        errors.append("rs1gt34 wire_map.tests must include delta_icc (ICCT mapped)")
    for tid, need_ch2 in (
        ("voh", True),
        ("vol", True),
        ("input_threshold", False),
        ("icc", False),
        ("ii", False),
        ("delta_icc", False),
    ):
        block = tests_wm.get(tid) if isinstance(tests_wm.get(tid), dict) else {}
        chans = [str(x) for x in (block.get("psu") or [])]
        has_ch2 = "CH2" in chans
        if need_ch2 and not has_ch2:
            errors.append(f"rs1gt34 {tid} wire_map must include PSU CH2 Y-load")
        if not need_ch2 and has_ch2:
            errors.append(f"rs1gt34 {tid} wire_map must not use PSU CH2 (Y-load is voh/vol only)")
    extra = pins_named_in_wire_map(m) - known_pin_names(m)
    if extra:
        errors.append(f"rs1gt34 wire_map invents nets {sorted(extra)}")
    voh = _table_sigs(
        yaml.get("voh_table") if isinstance(yaml.get("voh_table"), list) else [],
        "ioh_a",
        "spec_min",
    )
    vol = _table_sigs(
        yaml.get("vol_table") if isinstance(yaml.get("vol_table"), list) else [],
        "iol_a",
        "spec_max",
    )
    want_voh = {(round(a, 6), round(b, 9), round(c, 6)) for a, b, c in _DRAFT_34_VOH}
    want_vol = {(round(a, 6), round(b, 9), round(c, 6)) for a, b, c in _DRAFT_34_VOL}
    if voh != want_voh:
        errors.append(
            "rs1gt34 voh_table must match CONFIRMED card "
            "(100uA on merged vcc_list + named high-load only)"
        )
    if vol != want_vol:
        errors.append(
            "rs1gt34 vol_table must match CONFIRMED card "
            "(100uA on merged vcc_list + named high-load only)"
        )
    specs = {s.get("id"): s for s in load_part_specs("rs1gt34")}
    for row in yaml.get("voh_table") or []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "")
        spec = specs.get(sid) or {}
        if round(float(spec.get("min") or 0), 6) != round(float(row.get("spec_min") or 0), 6):
            errors.append(f"rs1gt34 limits {sid} min must match voh_table")
        mode = str(spec.get("pass_mode") or "").replace("_", "-")
        if mode not in ("min-only", "min"):
            errors.append(f"rs1gt34 {sid} pass_mode must be min-only")
        if str(spec.get("test") or "") != "voh":
            errors.append(f"rs1gt34 {sid} test must be voh")
    for row in yaml.get("vol_table") or []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "")
        spec = specs.get(sid) or {}
        if round(float(spec.get("max") or 0), 6) != round(float(row.get("spec_max") or 0), 6):
            errors.append(f"rs1gt34 limits {sid} max must match vol_table")
        mode = str(spec.get("pass_mode") or "").replace("_", "-")
        if mode not in ("max-only", "max"):
            errors.append(f"rs1gt34 {sid} pass_mode must be max-only")
        if str(spec.get("test") or "") != "vol":
            errors.append(f"rs1gt34 {sid} test must be vol")
    ii = specs.get("II_uA") or {}
    if round(float(ii.get("max") or 0), 6) != 1.0 or str(ii.get("test") or "") != "ii":
        errors.append("rs1gt34 II_uA must be max=1.0 test=ii (+25C judged)")
    ii_full = specs.get("II_FULL_uA") or {}
    if round(float(ii_full.get("max") or 0), 6) != 5.0 or ii_full.get("test"):
        errors.append("rs1gt34 II_FULL_uA must be max=5.0 with no test (Full documented)")
    icc = specs.get("ICC_uA") or {}
    if round(float(icc.get("max") or 0), 6) != 1.0 or str(icc.get("test") or "") != "icc":
        errors.append("rs1gt34 ICC_uA must be max=1.0 test=icc (+25C judged)")
    icc_full = specs.get("ICC_FULL_uA") or {}
    if round(float(icc_full.get("max") or 0), 6) != 10.0 or icc_full.get("test"):
        errors.append("rs1gt34 ICC_FULL_uA must be max=10.0 with no test (Full documented)")
    dicc = specs.get("DELTA_ICC_uA") or {}
    if round(float(dicc.get("max") or 0), 6) != 500.0 or str(dicc.get("test") or "") != "delta_icc":
        errors.append("rs1gt34 DELTA_ICC_uA must be max=500 test=delta_icc (ICCT Full)")
    ioff = specs.get("Ioff_uA") or {}
    if round(float(ioff.get("max") or 0), 6) != 1.0 or ioff.get("test"):
        errors.append("rs1gt34 Ioff_uA must be documented without test (VCC=0; not IOZ)")
    dc = m.dc_limits if isinstance(m.dc_limits, dict) else {}
    for which in ("voh", "vol", "ii", "icc", "delta_icc"):
        block = dc.get(which) if isinstance(dc.get(which), dict) else {}
        st = str(block.get("status") or "")
        if not is_datasheet_signed(st):
            errors.append(f"rs1gt34 dc_limits.{which} must be CONFIRMED, got {st!r}")
    icct = dc.get("ICCT_uA") if isinstance(dc.get("ICCT_uA"), dict) else {}
    try:
        one = float(icct.get("one_input_V"))
        vcc_icct = float(icct.get("vcc"))
        full = float(icct.get("Full") or icct.get("full") or 0)
    except (TypeError, ValueError):
        one = vcc_icct = full = None
    if one != 3.4 or vcc_icct != 5.5 or full != 500.0:
        errors.append(
            f"rs1gt34 ICCT_uA must be 500uA @5.5 one_in@3.4, got {icct}"
        )
    if str(icct.get("map_to") or "").strip().lower() != "delta_icc":
        errors.append("rs1gt34 ICCT_uA.map_to must be delta_icc")
    if lookup_pass_mode(m, "voh", "voh") != "min_only":
        errors.append("rs1gt34 pass_mode voh must be min_only")
    if lookup_pass_mode(m, "vol", "vol") != "max_only":
        errors.append("rs1gt34 pass_mode vol must be max_only")
    if lookup_pass_mode(m, "ii", "ii") != "max_only":
        errors.append("rs1gt34 pass_mode ii must be max_only")
    if lookup_pass_mode(m, "delta_icc", "delta_icc") != "max_only":
        errors.append("rs1gt34 pass_mode delta_icc must be max_only")
    if (m.recipe or {}).get("delta_offset_v") is not None:
        errors.append("rs1gt34 must not invent recipe.delta_offset_v (ICCT uses one_input_V=3.4)")
    if lookup_pass_mode(m, "VIH", "input_threshold") != "min_only":
        errors.append("rs1gt34 pass_mode VIH must be min_only")
    if lookup_pass_mode(m, "VIL", "input_threshold") != "max_only":
        errors.append("rs1gt34 pass_mode VIL must be max_only")
    search = (m.recipe or {}).get("search") if isinstance(m.recipe, dict) else {}
    if not isinstance(search, dict) or not search:
        errors.append("rs1gt34 recipe.search missing (limit-scaled first step, on-hit skip, no reverse)")
    else:
        vih = search.get("vih") if isinstance(search.get("vih"), dict) else {}
        vil = search.get("vil") if isinstance(search.get("vil"), dict) else {}
        if not vih.get("no_reverse_in_stage") or str(vih.get("direction") or "") != "up":
            errors.append("rs1gt34 recipe.search.vih must be up + no_reverse_in_stage")
        if not vil.get("no_reverse_in_stage") or str(vil.get("direction") or "") != "down":
            errors.append("rs1gt34 recipe.search.vil must be down + no_reverse_in_stage")
        on_hit = search.get("on_hit") if isinstance(search.get("on_hit"), dict) else {}
        if not on_hit.get("skip_rest_of_walk"):
            errors.append("rs1gt34 recipe.search.on_hit.skip_rest_of_walk must be true")
    from ate.tests.logic.excel_lock import (
        WORKBOOK_POLICY,
        ULTIMATE_POLICY,
        PRETTY_POLICY,
        bound_series_ids,
        excel_plots_status,
        golden_auto_policy,
        pretty_policy,
        ultimate_manual_policy,
        workbook_policy,
    )

    if golden_auto_policy(m) != WORKBOOK_POLICY:
        errors.append(
            f"rs1gt34 workbook_policy.auto/golden_auto must be {WORKBOOK_POLICY}, got {golden_auto_policy(m)!r}"
        )
    if ultimate_manual_policy(m) != ULTIMATE_POLICY:
        errors.append(
            f"rs1gt34 workbook_policy.ultimate_manual must be {ULTIMATE_POLICY}, got {ultimate_manual_policy(m)!r}"
        )
    if pretty_policy(m) != PRETTY_POLICY:
        errors.append(
            f"rs1gt34 workbook_policy.pretty must be {PRETTY_POLICY} (never auto), got {pretty_policy(m)!r}"
        )
    if workbook_policy(m) != WORKBOOK_POLICY:
        errors.append(
            f"rs1gt34 workbook_policy golden_auto token must be {WORKBOOK_POLICY}, got {workbook_policy(m)!r}"
        )
    plots_st = excel_plots_status(m).upper()
    if plots_st and plots_st != "CONFIRMED":
        errors.append(f"rs1gt34 excel_plots.status must be CONFIRMED, got {excel_plots_status(m)!r}")
    bound = bound_series_ids(m)
    if "ioz_vs_vcc" in bound:
        errors.append("rs1gt34 excel_plots must not bind ioz_vs_vcc (oe none)")
    if "delta_icc_vs_vcc" not in bound:
        errors.append("rs1gt34 excel_plots must bind delta_icc_vs_vcc (ICCT mapped)")
    want_series = {
        "vih_vs_vcc",
        "vil_vs_vcc",
        "icc_vs_vcc",
        "delta_icc_vs_vcc",
        "ii_vs_vcc",
        "voh_at_ioh",
        "vol_at_iol",
    }
    if bound != want_series:
        errors.append(
            f"rs1gt34 excel_plots series must be {sorted(want_series)}, got {sorted(bound)}"
        )
    plan = sim_icc_plan(m)
    if plan["n"] != 2:
        errors.append(f"rs1gt34 ICC corners must be 2^1=2, got {plan}")
    from ate.core.specs import enrich_measurement

    judged = enrich_measurement(
        {
            "id": "VIH_2p0V",
            "value": 1.5,
            "min": 1.0,
            "pass_mode": "min_only",
            "greenable": False,
        },
        test_id="input_threshold",
        part_key="rs1gt34",
    )
    if judged.get("result") == "pass":
        errors.append("Verify FAIL bar: unsigned/greenable=False VIH must not green as PASS")
    if claimed_signed_without_datasheet("UNCONFIRMED"):
        errors.append("UNCONFIRMED must not look signed")
    op_txt = _OPERATOR_DOC.read_text(encoding="utf-8") if _OPERATOR_DOC.is_file() else ""
    if "VOH/VOL unloaded" in op_txt:
        errors.append("LOGIC_DC_OPERATOR.md must not say RS1GT34 VOH/VOL unloaded")
    if "DRAFT / UNCONFIRMED until JH CONFIRM" in op_txt:
        errors.append(
            "LOGIC_DC_OPERATOR.md must promote RS1GT34 to CONFIRMED (Jian Hong 2026-09-18)"
        )
    if "ICCT" not in op_txt or "3.4" not in op_txt:
        errors.append(
            "LOGIC_DC_OPERATOR.md must name ICCT 500uA @5.5V one_in@3.4 "
            "(do not invent delta_offset_v=0.6)"
        )
    if "pretty" not in op_txt.lower() or "never auto" not in op_txt.lower():
        errors.append("LOGIC_DC_OPERATOR.md must name dual Excel: auto overwrite Version; pretty never auto")
    if "threshold_search" not in op_txt and "recipe.search" not in op_txt:
        errors.append("LOGIC_DC_OPERATOR.md must name recipe.search / threshold_search")
    owners = Path(__file__).resolve().parents[1] / "config" / "owners.yaml"
    inv = Path(__file__).resolve().parents[1] / "config" / "inventory.yaml"
    if "chun_tak" not in owners.read_text(encoding="utf-8"):
        errors.append("owners.yaml must name chun_tak for RS1GT34")
    inv_txt = inv.read_text(encoding="utf-8")
    if "Chun Tak" not in inv_txt or "Core AE OK" not in inv_txt:
        errors.append("inventory.yaml must note Chun Tak / Core AE OK")
    src = _LOGIC_DC.read_text(encoding="utf-8")
    if "lookup_vcc_grid_limits" not in src:
        errors.append("logic_dc.py input_threshold must apply per-VCC limits from vcc_grid")
    if "PSU_MSO" not in src:
        errors.append("logic_dc.py must keep YAML pin_drive on PSU_MSO (do not steal AWG CH1)")
    if "threshold_search" not in src or "run_search_stage" not in src:
        errors.append("logic_dc.py must wire recipe.search via threshold_search")
    if "one_input_V" not in src:
        errors.append("logic_dc.py delta_icc must use ICCT one_input_V (not invent 0.6)")
    model_src = _MODEL.read_text(encoding="utf-8")
    if "merge_vcc_grid" not in model_src or "lookup_vcc_grid_limits" not in model_src:
        errors.append("product_model must merge vcc_grid fixed+ranges and lookup per-VCC limits")
    return errors


def _threshold_search_ok() -> list[str]:
    """Verify FAIL bars: reverse search, first step > |limit|, on-hit skip, invent 0.6, ioz, unsigned green."""
    from ate.core.specs import enrich_measurement
    from ate.tests.logic import logic_dc as ldc
    from ate.tests.logic.excel_lock import PRETTY_POLICY, is_ultimate_path, pretty_policy
    from ate.tests.logic.threshold_search import (
        SearchError,
        SearchReverseError,
        first_step,
        run_search_stage,
        stage_points,
        step_ladder,
    )

    errors: list[str] = []
    if not _THRESHOLD_SEARCH.is_file():
        return ["threshold_search.py missing (recipe.search helper)"]
    errors += _no_part_name_ifs(_THRESHOLD_SEARCH)
    ladder = [0.5, 0.2, 0.1, 0.05, 0.01]
    if abs(first_step(ladder, 1.0) - 0.5) > 1e-12:
        errors.append(
            f"Verify FAIL bar: VIH |limit| 1.0 first_step must be 0.5, got {first_step(ladder, 1.0)}"
        )
    if abs(first_step(ladder, 0.3) - 0.2) > 1e-12:
        errors.append(
            f"Verify FAIL bar: VIL |limit| 0.3 first_step must be 0.2 not 0.5, got {first_step(ladder, 0.3)}"
        )
    try:
        first_step([1.0, 0.8], 0.3)
        errors.append("Verify FAIL bar: first step > |limit| must FAIL (no invent smaller than ladder)")
    except SearchError:
        pass
    except Exception as exc:
        errors.append(
            f"first step > |limit| must raise SearchError, got {type(exc).__name__}: {exc}"
        )
    try:
        stage_points(1.0, 0.0, 0.1, True)
        errors.append("Verify FAIL bar: VIH reverse (end < arm) must raise SearchReverseError")
    except SearchReverseError:
        pass
    except Exception as exc:
        errors.append(
            f"VIH reverse must raise SearchReverseError, got {type(exc).__name__}: {exc}"
        )
    try:
        stage_points(0.0, 1.0, 0.1, False)
        errors.append("Verify FAIL bar: VIL reverse (end > arm) must raise SearchReverseError")
    except SearchReverseError:
        pass
    except Exception as exc:
        errors.append(
            f"VIL reverse must raise SearchReverseError, got {type(exc).__name__}: {exc}"
        )
    m = load_product_model("rs1gt34")
    if m is None:
        errors.append("rs1gt34 product_model missing for recipe.search SIM")
        return errors
    search = (m.recipe or {}).get("search") if isinstance(m.recipe, dict) else {}
    if not isinstance(search, dict) or not search:
        errors.append("rs1gt34 recipe.search missing for threshold_search SIM")
        return errors
    try:
        lad = step_ladder(search)
    except SearchError as exc:
        errors.append(f"rs1gt34 recipe.search ladder: {exc}")
        return errors
    lim20 = lookup_vcc_grid_limits(m, 2.0) or {}
    try:
        vih_first = first_step(lad, lim20.get("VIH_min_V"))
        vil_first = first_step(lad, lim20.get("VIL_max_V"))
    except SearchError as exc:
        errors.append(f"rs1gt34 first_step from vcc_grid: {exc}")
        vih_first = vil_first = None
    if vih_first is not None and abs(vih_first - 0.5) > 1e-12:
        errors.append(
            f"Verify FAIL bar: rs1gt34 VIH@2.0 |limit| 1.0 first_step must be 0.5, got {vih_first}"
        )
    if vil_first is not None and abs(vil_first - 0.2) > 1e-12:
        errors.append(
            f"Verify FAIL bar: rs1gt34 VIL@2.0 |limit| 0.3 first_step must be 0.2 not 0.5, got {vil_first}"
        )
    blob = dict(search)
    on_hit = dict(blob.get("on_hit") if isinstance(blob.get("on_hit"), dict) else {})
    on_hit["skip_rest_of_walk"] = True
    on_hit["next_smaller_step"] = False
    blob["on_hit"] = on_hit

    def _vih(vin: float) -> float:
        return 2.0 if float(vin) >= 1.15 else 0.0

    r = run_search_stage(
        _vih, vcc=2.0, rising=True, limit=1.0, search=blob, y_expect="track"
    )
    if r.first_step is not None and abs(r.first_step - 0.5) > 1e-12:
        errors.append(f"search first_step VIH must be 0.5, got {r.first_step}")
    if any(abs(float(v) - 2.0) < 1e-9 for v in r.visited):
        errors.append(
            "Verify FAIL bar: on-hit skip must not visit VCC after coarse VIH hit"
        )
    noskip = dict(blob)
    on_hit_n = dict(on_hit)
    on_hit_n["skip_rest_of_walk"] = False
    noskip["on_hit"] = on_hit_n
    r_n = run_search_stage(
        _vih, vcc=2.0, rising=True, limit=1.0, search=noskip, y_expect="track"
    )
    if not any(abs(float(v) - 2.0) < 1e-9 for v in r_n.visited):
        errors.append("SIM control: without skip, coarse VIH walk must still reach VCC")
    rev = dict(search)
    vih_rev = dict(rev.get("vih") if isinstance(rev.get("vih"), dict) else {})
    vih_rev["direction"] = "down"
    rev["vih"] = vih_rev
    try:
        run_search_stage(
            lambda _v: 0.0, vcc=2.0, rising=True, limit=1.0, search=rev, y_expect="track"
        )
        errors.append("Verify FAIL bar: reverse VIH search must raise SearchReverseError")
    except SearchReverseError:
        pass
    except Exception as exc:
        errors.append(
            f"reverse VIH search must raise SearchReverseError, got {type(exc).__name__}: {exc}"
        )
    force = ldc._delta_force_v(m, 5.5)
    if abs(float(force) - 3.4) > 1e-9:
        errors.append(f"rs1gt34 delta_icc force must be ICCT one_in 3.4, got {force}")
    if abs(float(force) - 4.9) < 1e-9:
        errors.append("Verify FAIL bar: invent 0.6 (VCC-0.6) must not be the ICCT force")
    try:
        vccs = ldc._delta_vccs(_params(part="rs1gt34", vcc=5.5), m)
    except Exception as exc:
        errors.append(f"rs1gt34 _delta_vccs: {type(exc).__name__}: {exc}")
        vccs = []
    if [round(float(x), 6) for x in vccs] != [5.5]:
        errors.append(f"rs1gt34 ICCT vcc must restrict delta_icc to [5.5], got {vccs}")
    try:
        ldc._run_ioz(None, _params(part="rs1gt34", vcc=5.0))
        errors.append("Verify FAIL bar: ioz on rs1gt34 (oe none) must raise")
    except RuntimeError as exc:
        if "not applicable" not in str(exc).lower() and "oe is none" not in str(exc).lower():
            errors.append(f"ioz rs1gt34 should say oe is none / not applicable, got {exc!r}")
    except Exception as exc:
        errors.append(f"ioz rs1gt34 must raise RuntimeError, got {type(exc).__name__}: {exc}")
    judged = enrich_measurement(
        {
            "id": "VIH_2p0V",
            "value": 1.5,
            "min": 1.0,
            "pass_mode": "min_only",
            "greenable": False,
        },
        test_id="input_threshold",
        part_key="rs1gt34",
    )
    if judged.get("result") == "pass":
        errors.append(
            "Verify FAIL bar: unsigned/greenable=False VIH must not green as PASS"
        )
    if pretty_policy(m) != PRETTY_POLICY:
        errors.append(
            f"Verify FAIL bar: pretty must be {PRETTY_POLICY} (never auto), got {pretty_policy(m)!r}"
        )
    if not is_ultimate_path("pretty.xlsx"):
        errors.append("Verify FAIL bar: pretty.xlsx must never be an auto dest")
    src = _LOGIC_DC.read_text(encoding="utf-8")
    if "run_search_stage" not in src or "threshold_search" not in src:
        errors.append("logic_dc.py must call threshold_search.run_search_stage")
    load_family("logic")
    th = get("input_threshold")
    if th is None or th.run is not ldc._run_input_threshold:
        errors.append("input_threshold.run must stay logic_dc._run_input_threshold")
    return errors


def _enabled_voh_vol_tables_ok() -> list[str]:
    """Enabled voh/vol without table rows is enabled-but-unrunnable. FAIL-closed."""
    from ate.tests.logic import logic_dc as ldc

    errors: list[str] = []
    for path in sorted(PARTS_DIR.glob("*.yaml")):
        key = path.stem.lower()
        if not has_product_model(key):
            continue
        en = {str(x).strip() for x in (enabled_tests_for_part(key) or []) if str(x).strip()}
        if "voh" in en and not ldc._voh_vol_table(key, "voh"):
            errors.append(f"{key}: voh enabled but no voh_table rows")
        if "vol" in en and not ldc._voh_vol_table(key, "vol"):
            errors.append(f"{key}: vol enabled but no vol_table rows")
    return errors


def _operator_doc_ok() -> list[str]:
    """Operator bench doc exists. DEMO/SIM is not a reproduce claim. No invented cells."""
    errors: list[str] = []
    if not _OPERATOR_DOC.is_file():
        return ["docs/LOGIC_DC_OPERATOR.md missing (operator bench; not a reproduce claim)"]
    text = _OPERATOR_DOC.read_text(encoding="utf-8")
    if "not" not in text.lower() or "reproduce" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must say DEMO/SIM is not a reproduce claim")
    if "python -m ate.core.check_logic_dc" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name python -m ate.core.check_logic_dc")
    if "sheet_map" not in text or "campaign_outline" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must use sheet_map / campaign_outline only (never invent cells)")
    if "invent" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must forbid inventing Excel cells")
    if "sessions/report.json" not in text.replace(" ", ""):
        # allow sessions/report.json with or without backticks
        if "report.json" not in text:
            errors.append("LOGIC_DC_OPERATOR.md must name sessions/report.json")
    if "datalog.md" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name STS datalog.md")
    if "report.pdf" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name Version-root report.pdf")
    if "dual_channel_continue" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name recipe.dual_channel_continue")
    if "CHA then CHB" not in text and "CHA then Channel B" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name CHA then CHB Continue")
    if "datapoints.csv" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name golden_auto datapoints.csv sidecar")
    if "LOGIC_DC_DUAL_CHANNEL.md" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must point at docs/LOGIC_DC_DUAL_CHANNEL.md")
    if "records/" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name {test}/DUT_n/records/")
    if "START.bat" not in text or "127.0.0.1:5174" not in text or "8766" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name START.bat, UI 5174, worker 8766")
    if "Ctrl+F5" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name Ctrl+F5 after pull")
    if "idle-restart" not in text.lower() and "restart_ate_worker" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name idle-restart worker")
    if "Open Session" not in text:
        errors.append("LOGIC_DC_OPERATOR.md checklist must include Open Session")
    if "RS1G97" not in text or "RS1G126" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must checklist RS1G97 and RS1G126")
    if "DMM-on-VCC" not in text or "2^n" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must cover ICC DMM-on-VCC 2^n")
    if "hard-FAIL" not in text and "hard-fail" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must cover settle timeout hard-FAIL")
    if "VOH" not in text or "min" not in text.lower() or "VOL" not in text or "max" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must confirm VOH >= min / VOL <= max vs table")
    if "IOZ" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must cover IOZ if OE")
    if "stable_eps_A" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document stable_eps_A (current; not volts)")
    if "FAIL-closed" not in text and "fail-closed" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must say tight current settle is FAIL-closed without stable_eps_A")
    if "NON_TIGHT" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document settle=NON_TIGHT when stable_eps_A is null")
    if "PaddleOCR" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name PaddleOCR (chosen OCR path)")
    if "baidu" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must say do not install Baidu unless asked")
    if "card_fields.schema.yaml" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must link docs/datasheet/card_fields.schema.yaml")
    if "TestSpec" not in text or "Recipe" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must map TestSpec to OOP (Part/Pin/TruthTable/Isolation/Limit/Recipe)")
    if "See Lim" not in text or "Ariff" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must note See Lim/Ariff as read-only refs")
    if "invent a ua" not in text.lower().replace("µ", "u"):
        errors.append("LOGIC_DC_OPERATOR.md must forbid inventing a uA current-settle epsilon")
    if "wire_map" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document wire_map Continue prompts")
    if "vcc_grid" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document vcc_grid / Customise Parameters")
    if "PSU_MSO" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document PSU_MSO (hide Freq/Amp)")
    if "RS1GT34" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must checklist RS1GT34")
    if "2026-09-18" not in text or "CONFIRMED" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must say RS1GT34 CONFIRMED Jian Hong 2026-09-18")
    if "pretty" not in text.lower() or "never auto" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must name dual Excel auto overwrite / pretty never auto")
    if "recipe.search" not in text and "threshold_search" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name recipe.search / threshold_search")
    if "DRAFT / UNCONFIRMED until JH CONFIRM" in text:
        errors.append(
            "LOGIC_DC_OPERATOR.md must not keep RS1GT34 DRAFT / UNCONFIRMED until JH CONFIRM"
        )
    if "data_paths" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document data_paths")
    if "invent nets" not in text.lower() and "invent a net" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must forbid inventing nets")
    if "settle_prompt" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must document settle_prompt (show wait)")
    if "Human Continue" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must say Human Continue after wire-map verify")
    if "copy-ready" not in text.lower() and "copy ready" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must include a copy-ready Version folder")
    if text.lower().count("start.bat") < 4:
        errors.append("LOGIC_DC_OPERATOR.md must name START.bat everywhere (Version folder + DEMO + HUMAN + console + checklist)")
    if "#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/workbook/" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must show Excel #Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/workbook/")
    if "one_per_version_overwrite" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name workbook_policy one_per_version_overwrite")
    if "golden_auto" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name golden_auto Version workbook")
    if "ultimate_manual" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name ultimate_manual jot workbook")
    if "never_auto_write" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name ultimate_manual never_auto_write")
    if "sessions/csv" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name sessions/csv (Path B auto CSV)")
    if "path_b_write.json" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name sessions/path_b_write.json fill log")
    if "RS1G08" not in text or "RS1G07" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name next Path B stubs RS1G08 and RS1G07")
    if "excel_plots" not in text:
        errors.append("LOGIC_DC_OPERATOR.md must name excel_plots (card-backed series only)")
    if "orphan" not in text.lower():
        errors.append("LOGIC_DC_OPERATOR.md must forbid orphan second xlsx books")
    if not re.search(r"HEAD SHA.*[`']?[0-9a-f]{7,40}", text, re.I | re.S):
        errors.append("LOGIC_DC_OPERATOR.md must list PR HEAD SHA")
    logic = Path(__file__).resolve().parents[2] / "docs" / "LOGIC_DC.md"
    if "LOGIC_DC_OPERATOR.md" not in logic.read_text(encoding="utf-8"):
        errors.append("docs/LOGIC_DC.md must point at LOGIC_DC_OPERATOR.md")
    return errors


def _registry_ok() -> list[str]:
    errors: list[str] = []
    load_family("logic")
    ids = {t.id for t in all_tests()}
    missing = [i for i in _PATH_B_IDS if i not in ids]
    if missing:
        errors.append(f"logic registry missing Path B ids {missing}")
    th = get("input_threshold")
    vth = get("vth")
    if th is None or vth is None or th.run is not vth.run:
        errors.append("vth must be the same run as input_threshold")
    icc = get("icc")
    if icc is None or icc.dual_channel:
        errors.append("icc must be registered dual_channel=False")
    from ate.tests.logic import logic_dc as ldc
    from ate.tests.logic import dc as dcmod

    if th.run is not ldc._run_input_threshold:
        errors.append("input_threshold must be logic_dc._run_input_threshold")
    if dcmod._run_icc is not ldc._run_icc:
        errors.append("dc.py must be the same runner as logic_dc.py (no per-chip fork)")
    if get("delta_icc") is None or get("delta_icc").run is not ldc._run_delta_icc:
        errors.append("delta_icc must be logic_dc._run_delta_icc")
    if get("ioz") is None or get("ioz").run is not ldc._run_ioz:
        errors.append("ioz must be logic_dc._run_ioz")
    p = _params(part="rs1g08", vcc=1.65, current_limit_a=0.05)
    try:
        ldc._run_ioz(None, p)
        errors.append("ioz on rs1g08 (oe none) must raise")
    except RuntimeError as exc:
        if "not applicable" not in str(exc).lower() and "oe is none" not in str(exc).lower():
            errors.append(f"ioz rs1g08 should say not applicable, got {exc!r}")
    try:
        ldc._run_input_threshold(None, _params(part="rs1g97", vcc=5.0))
        errors.append("input_threshold must require instruments")
    except RuntimeError as exc:
        if "Missing instruments" not in str(exc):
            errors.append(f"input_threshold should say missing instruments, got {exc!r}")
    try:
        ldc._run_icc_dispatch(None, _params(part="rs1g07", vcc=5.0))
        errors.append("icc on part without product_model / dual-rail must raise")
    except RuntimeError:
        pass
    if has_product_model("rs0204"):
        errors.append("rs0204 must not grow a Path B product_model (dual-rail stays rs0204.py)")
    return errors


def _seelim_wrap_ok() -> list[str]:
    """Locator exists; family load must not execute goldens or scrape limits."""
    errors: list[str] = []
    src = Path(__file__).resolve().parents[1] / "tests" / "logic" / "seelim_dc.py"
    if not src.is_file():
        return ["seelim_dc.py missing -- wrap goldens/see_lin/<PART>/current_tests.py"]
    text = src.read_text(encoding="utf-8")
    if re.search(r"(?m)^\s*(?:import\s+Lim\b|from\s+Lim\b)", text):
        errors.append("seelim_dc.py must not import Lim.*")
    if "goldens" not in text or "see_lin" not in text:
        errors.append("seelim_dc.py must look up goldens/see_lin/<PART>/current_tests.py")
    if "See Lim Repo" not in text:
        errors.append("seelim_dc.py must fall back to Downloads/See Lim Repo")
    visa_before = "pyvisa" in sys.modules
    from ate.tests.logic.seelim_dc import resolve_current_tests

    missing = resolve_current_tests("rs1g97")
    if missing is not None and not Path(missing).is_file():
        errors.append("resolve_current_tests must return an existing file or None")
    if not visa_before and "pyvisa" in sys.modules:
        errors.append("seelim_dc locator must not import pyvisa")
    return errors


def _panel_ok() -> list[str]:
    errors: list[str] = []
    web = Path(__file__).resolve().parents[1] / "ui" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    for need in (
        'id="panel-logic-dc"',
        'id="logic-dc-truth"',
        'id="logic-dc-isolation"',
        'id="logic-dc-pass-mode"',
        'id="logic-dc-vcc-list"',
        'id="logic-dc-gaps"',
        'id="btn-save-logic-dc"',
        'id="btn-save-test-params"',
        'id="logic-dc-body"',
    ):
        if need not in html:
            errors.append(f"Logic DC panel missing {need}")
    if 'id="add-test-format"' not in html:
        errors.append("STANDARD FORMAT checklist (#add-test-format) missing")
    if "loadLogicDcPanel" not in js or "get_product_model" not in js:
        errors.append("app.js must load Logic DC product_model")
    if "saveLogicDcPanel" not in js:
        errors.append("app.js must save Logic DC product_model")
    if "renderLogicDc" not in js or "save_test_params" not in js:
        errors.append("app.js must visualise recipe + save Version overlay")
    if "icc_corner_rows" not in js or "Enabled tests" not in js or "fail-open" not in js:
        errors.append("app.js must visualise enabled tests, ICC corners, fail-open")
    if "logic-dc-stable-eps-a" not in js or "stable_eps_A" not in js:
        errors.append("Logic DC panel must edit stable_eps_A (overlay; null = NON_TIGHT)")
    if "Customise Parameters" not in js:
        errors.append("Logic DC panel must show Customise Parameters (not xyflow)")
    if "FIXED POINTS" not in js or "RANGE SWEEPS" not in js:
        errors.append("Customise Parameters must have FIXED POINTS chips and RANGE SWEEPS")
    if "PSU_MSO" not in js or "logic-dc-vcc-preview" not in js:
        errors.append("Customise Parameters must preview merged vcc_list and stimulus PSU_MSO vs AWG")
    if "vcc_grid" not in js:
        errors.append("app.js must save vcc_grid to Version overlay")
    if "xyflow" in js.lower() and "no xyflow" not in js.lower():
        errors.append("Customise Parameters must not introduce xyflow")
    if "freq-label" not in html:
        errors.append("PSU_MSO must be able to hide Freq/Amp labels")
    db = Path(__file__).resolve().parents[1] / "core" / "database.py"
    db_txt = db.read_text(encoding="utf-8")
    if '"vcc_grid"' not in db_txt or '"sample_size"' not in db_txt:
        errors.append("save_test_params must allow vcc_grid and sample_size")
    if "data-card-field" not in js or "deleted_fields" not in js:
        errors.append("Logic DC panel must bind per-field assign/edit/delete to card_fields")
    if "card_fields" not in js:
        errors.append("app.js must render card_fields from OOP_SCHEMA")
    if not CARD_FIELDS_SCHEMA_PATH.is_file():
        errors.append("docs/datasheet/card_fields.schema.yaml missing")
    else:
        schema_txt = CARD_FIELDS_SCHEMA_PATH.read_text(encoding="utf-8")
        for need in ("Part", "Pin", "TruthTable", "Isolation", "Limit", "Recipe", "paddleocr"):
            if need not in schema_txt:
                errors.append(f"card_fields.schema.yaml must name {need}")
        if "baidu" not in schema_txt.lower():
            errors.append("card_fields.schema.yaml must forbid Baidu unless asked")
    model_src = _MODEL.read_text(encoding="utf-8")
    if "load_card_fields_schema" not in model_src or "panel_save_keys" not in model_src:
        errors.append("save_product_model must bind keys from card_fields.schema.yaml")
    if "_PANEL_SAVE_KEYS" in model_src:
        errors.append("product_model must not keep an opaque _PANEL_SAVE_KEYS tuple")
    try:
        schema = load_card_fields_schema()
        objs = schema.get("oop_objects") or []
        for need in ("Part", "Pin", "TruthTable", "Isolation", "Limit", "Recipe"):
            if need not in objs:
                errors.append(f"card_fields.schema.yaml oop_objects missing {need}")
        if str(schema.get("ocr", {}).get("engine") or "").lower() != "paddleocr":
            errors.append("card_fields.schema.yaml ocr.engine must be paddleocr")
        keys = panel_save_keys()
        for need in ("pins", "recipe", "recipe.stable_eps_A", "recipe.search", "recipe.dual_channel_continue", "recipe.channels", "truth_table", "oe", "schmitt", "wire_map", "settle_prompt", "data_paths", "vcc_grid", "excel_plots", "workbook_policy"):
            if need not in keys:
                errors.append(f"panel_save_keys missing {need}")
    except Exception as exc:
        errors.append(f"load_card_fields_schema failed: {exc!r}")
    if judge_value(1, None, None, pass_mode="fail-open") != "fail":
        errors.append("fail-open with no limits must fail")
    srv = Path(__file__).resolve().parents[1] / "worker" / "server.py"
    text = srv.read_text(encoding="utf-8")
    if 'method == "get_product_model"' not in text or 'method == "save_product_model"' not in text:
        errors.append("worker must expose get_product_model / save_product_model")
    if 'method == "save_test_params"' not in text:
        errors.append("worker must expose save_test_params")
    return errors


def _scale_and_overlay_ok() -> list[str]:
    """2-input vs 3-input corners on the same Path B ids. Visa-free SIM."""
    errors: list[str] = []
    m08 = load_product_model("rs1g08")
    m97 = load_product_model("rs1g97")
    m126 = load_product_model("rs1g126")
    if m08 is None or m97 is None or m126 is None:
        return ["scale check needs rs1g08/rs1g97/rs1g126 product_model"]
    p08 = sim_icc_plan(m08)
    p97 = sim_icc_plan(m97)
    p126 = sim_icc_plan(m126)
    if p08["n"] != 4:
        errors.append(f"rs1g08 ICC corners must be 2^2=4, got {p08}")
    if p97["n"] != 8:
        errors.append(f"rs1g97 ICC corners must be 2^3=8, got {p97}")
    if p126["n"] != 4:
        errors.append(f"rs1g126 ICC corners must be 2^(A+OE)=4, got {p126}")
    m07 = load_product_model("rs1g07")
    if m07 is None:
        errors.append("rs1g07 product_model missing (Path B stub)")
    else:
        p07 = sim_icc_plan(m07)
        if p07["n"] != 2:
            errors.append(f"rs1g07 ICC corners must be 2^1=2, got {p07}")
    over = load_product_model("rs1g08", overlay={"vcc_list": [3.3], "pass_mode": {"ICC_uA": "max-only"}})
    if over is None or over.vcc_list != [3.3]:
        errors.append(f"test_params overlay must replace vcc_list, got {None if over is None else over.vcc_list}")
    if m08.vcc_list == [3.3] and len(m08.vcc_list) == 1:
        errors.append("part yaml vcc_list must stay the default without overlay")
    pins = ["A", "B", "C"]
    rows = []
    for vec in iter_logic_corners(pins):
        y = "H" if all(vec[p] == "H" for p in pins) else "L"
        rows.append({**vec, "Y": y})
    derived = derive_isolation(logic_inputs=pins, truth_table=rows)
    a = derived.get("A") or []
    if not any(p.fix.get("B") == "H" and p.fix.get("C") == "H" and p.y_expect == "track" for p in a):
        errors.append(f"3-input AND derive A must track with B=H C=H, got {a}")
    if len(iter_logic_corners(pins)) != 8:
        errors.append("3-input AND corners must be 8")
    specs = {s.get("id"): s for s in load_part_specs("rs1g08")}
    voh_mode = str(specs.get("VOH_2p0V", {}).get("pass_mode") or "").replace("_", "-")
    if voh_mode != "min-only":
        errors.append("rs1g08 VOH pass_mode must be min-only")
    icc_mode = str(specs.get("ICC_uA", {}).get("pass_mode") or "").replace("_", "-")
    if icc_mode != "max-only":
        errors.append("rs1g08 ICC_uA pass_mode must be max-only")
    if judge_value(4.9, 4.8, 9, pass_mode="min-only") != "pass":
        errors.append("min-only must ignore max")
    if judge_value(0.2, 1, 0.5, pass_mode="max-only") != "pass":
        errors.append("max-only must ignore min")
    if infer_pass_mode({"id": "VIH_V", "min": 2.0}) != "min-only":
        errors.append("VIH default pass_mode min-only")
    over_specs = {s.get("id"): s for s in load_part_specs("rs1g08", overlay={"pass_mode": {"ICC_uA": "fail-open"}})}
    if str(over_specs.get("ICC_uA", {}).get("pass_mode") or "") != "fail-open":
        errors.append("test_params overlay must set pass_mode fail-open")
    return errors


def _run_is_stub(run) -> str:
    """Empty / NotImplementedError-only body. Callable wraps are not stubs."""
    if run is None or not callable(run):
        return "run is not callable"
    try:
        src = inspect.getsource(inspect.unwrap(run))
    except (OSError, TypeError):
        return ""
    try:
        tree = ast.parse(textwrap.dedent(src))
    except SyntaxError:
        if re.search(r"raise\s+NotImplementedError", src):
            return "NotImplementedError stub"
        return ""
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            fn = node
            break
    if fn is None:
        if re.search(r"raise\s+NotImplementedError", src):
            return "NotImplementedError stub"
        return ""
    stmts = []
    for node in fn.body:
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
            continue
        if isinstance(node, ast.Pass):
            stmts.append(node)
            continue
        stmts.append(node)
    if not stmts:
        return "empty stub"
    if len(stmts) == 1 and isinstance(stmts[0], ast.Pass):
        return "pass-only stub"
    if len(stmts) == 1 and isinstance(stmts[0], ast.Raise):
        exc = stmts[0].exc
        names: list[str] = []
        if isinstance(exc, ast.Name):
            names.append(exc.id)
        elif isinstance(exc, ast.Call):
            func = exc.func
            if isinstance(func, ast.Name):
                names.append(func.id)
        if any(n in ("NotImplementedError",) for n in names):
            return "NotImplementedError stub"
        if any(n == "RuntimeError" for n in names):
            if re.search(r"(?i)\bstub\b", src):
                return "RuntimeError stub"
    if re.search(r"raise\s+NotImplementedError", src) and "not a stub" not in src.lower():
        # real bodies may mention the word in comments; only fail if raise is present
        for node in ast.walk(fn):
            if isinstance(node, ast.Raise):
                exc = node.exc
                if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                    return "NotImplementedError stub"
                if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                    if exc.func.id == "NotImplementedError":
                        return "NotImplementedError stub"
    return ""


def _handoff_ok() -> list[str]:
    """AE/FAE: every enabled 97/126 test has wire_map + data_paths. Never invent nets."""
    errors: list[str] = []
    wraps = Path(__file__).resolve().parents[1] / "tests" / "logic" / "wraps.py"
    runner = Path(__file__).resolve().parents[1] / "core" / "runner.py"
    for part in ("rs1g97", "rs1g126", "rs1gt34"):
        m = load_product_model(part)
        if m is None:
            errors.append(f"{part} product_model missing for AE/FAE handoff")
            continue
        missing = missing_data_path_keys(m)
        if missing:
            errors.append(f"{part}: missing data_paths {missing}")
        raw_paths = m.data_paths if isinstance(m.data_paths, dict) else {}
        for key, tmpl in DATA_PATH_TEMPLATES.items():
            got = str(raw_paths.get(key) or "").strip()
            if got != tmpl:
                errors.append(
                    f"{part} data_paths.{key} must be {tmpl!r} (folder template; do not invent Excel cells)"
                )
        extra = pins_named_in_wire_map(m) - known_pin_names(m)
        if extra:
            errors.append(
                f"{part} wire_map invents nets {sorted(extra)} (CONFIRMED pins only)"
            )
        enabled = [
            str(x).strip()
            for x in (enabled_tests_for_part(part) or [])
            if str(x).strip()
        ]
        for tid in enabled:
            try:
                block = wire_map_for_test(m, tid)
            except RuntimeError:
                errors.append(f"{part}: enabled {tid} has empty wire_map")
                continue
            if not block:
                errors.append(f"{part}: enabled {tid} has empty wire_map")
        probe = "icc" if "icc" in enabled else (enabled[0] if enabled else "")
        if probe:
            try:
                blob = "\n".join(format_handoff_begin(m, probe))
            except RuntimeError as exc:
                errors.append(f"{part} format_handoff_begin: {exc}")
            else:
                if "PSU CH1" not in blob or "Human Continue" not in blob:
                    errors.append(f"{part} handoff must surface PSU CH->pin + Human Continue")
                if "Stimulus" not in blob:
                    errors.append(f"{part} handoff must surface Stimulus")
                if "Settle" not in blob or "wait" not in blob.lower():
                    errors.append(f"{part} handoff must surface Settle wait")
                if "Measure" not in blob:
                    errors.append(f"{part} handoff must surface Measure + pass_mode")
                if "NON_TIGHT" not in blob and "tight" not in blob.lower():
                    errors.append(f"{part} handoff settle must name NON_TIGHT or tight")
                if "golden_auto" not in blob or "ultimate_manual" not in blob:
                    errors.append(
                        f"{part} handoff must bind Excel fill/plot to golden_auto "
                        "(never ultimate_manual)"
                    )
    model_src = _MODEL.read_text(encoding="utf-8")
    ldc_src = _LOGIC_DC.read_text(encoding="utf-8")
    if "path_b_handoff" not in model_src:
        errors.append("product_model must define path_b_handoff")
    if "path_b_handoff" not in ldc_src:
        errors.append("logic_dc.py must call path_b_handoff on Path B runs")
    if not wraps.is_file() or "path_b_handoff" not in wraps.read_text(encoding="utf-8"):
        errors.append("wraps.py must surface path_b_handoff for Path B AC ids")
    runner_src = runner.read_text(encoding="utf-8") if runner.is_file() else ""
    if "checklist=None" not in runner_src and "checklist = None" not in runner_src:
        errors.append("runner pause_hook must accept checklist (Logic wire_map, not OpAmp-only)")
    if "format_fail_lines" not in runner_src:
        errors.append("runner FAIL popup must prompt scope capture / attach path")
    if "do not invent nets" not in model_src.lower():
        errors.append("product_model handoff must say do not invent nets")
    return errors


def _runnable_ok() -> list[str]:
    """Every enabled_tests id must have a registered TestSpec with callable run."""
    errors: list[str] = []
    load_family("logic")
    parts: list[str] = []
    for path in sorted(PARTS_DIR.glob("*.yaml")):
        key = path.stem.lower()
        if has_product_model(key):
            parts.append(key)
    if "rs1g97" not in parts or "rs1g126" not in parts:
        errors.append("runnable gate needs Path B parts rs1g97 and rs1g126")
    for part in parts:
        ids = [str(x).strip() for x in (enabled_tests_for_part(part) or []) if str(x).strip()]
        for tid in ids:
            spec = get(tid)
            if spec is None:
                errors.append(f"{part}: enabled {tid} has no registered TestSpec")
                continue
            why = _run_is_stub(spec.run)
            if why:
                errors.append(f"{part}: enabled {tid} is enabled-but-unrunnable ({why})")
            elif not callable(spec.run):
                errors.append(f"{part}: enabled {tid} TestSpec.run is not callable")
    return errors


def _excel_lock_ok() -> list[str]:
    """golden_auto Version xlsx. Never write ultimate_manual. Invented columns FAIL."""
    from ate.reporting.session_values import fill_workbook_from_report
    from ate.tests.logic import excel_lock as el

    errors: list[str] = []
    lock_src = Path(__file__).resolve().parents[1] / "tests" / "logic" / "excel_lock.py"
    src = lock_src.read_text(encoding="utf-8")
    if "one_per_version_overwrite" not in src:
        errors.append("excel_lock.py must name one_per_version_overwrite")
    if "golden_auto" not in src or "ultimate_manual" not in src:
        errors.append("excel_lock.py must split golden_auto vs ultimate_manual")
    if "never_auto_write" not in src:
        errors.append("excel_lock.py must name never_auto_write")
    if "datapoints.csv" not in src or "write_datapoints_csv" not in src:
        errors.append("excel_lock.py must write full datapoints CSV alongside golden_auto")
    if "PRETTY_POLICY" not in src or "pretty" not in src:
        errors.append("excel_lock.py must name pretty never auto")
    if "write_path_b_csv" not in src or "path_b_write.json" not in src:
        errors.append("excel_lock.py must write sessions/csv + path_b_write.json")
    if "sessions/csv" not in src:
        errors.append("excel_lock.py CSV dest must be sessions/csv")
    runner_src = Path(__file__).resolve().parents[1] / "core" / "runner.py"
    rtxt = runner_src.read_text(encoding="utf-8")
    if "bind_golden_auto" not in rtxt or "coerce_golden_auto_lab_report" not in rtxt:
        errors.append("Open Session / START must bind fill/plot to golden_auto Version path")
    wtxt = (
        Path(__file__).resolve().parents[1] / "worker" / "server.py"
    ).read_text(encoding="utf-8")
    if "coerce_golden_auto_lab_report" not in wtxt:
        errors.append("START worker must bind fill/plot to golden_auto Version path")
    dtxt = (
        Path(__file__).resolve().parents[1] / "core" / "database.py"
    ).read_text(encoding="utf-8")
    if "bind_golden_auto" not in dtxt:
        errors.append("lab_report_path must bind fill/plot to golden_auto Version path")
    for line in src.splitlines():
        if "_filled.xlsx" in line and re.search(r"\.save\s*\(", line):
            errors.append("excel_lock.py must not save _filled.xlsx")
    sv_txt = (
        Path(__file__).resolve().parents[1] / "reporting" / "session_values.py"
    ).read_text(encoding="utf-8")
    i_lock = sv_txt.find("uses_excel_lock")
    i_none = sv_txt.find('"no_workbook"')
    if i_lock < 0 or i_none < 0 or i_lock > i_none:
        errors.append("Path B excel lock must run before no_workbook (create the one book)")
    if "gbw" in el.ALLOWED_SERIES or "noise" in el.ALLOWED_SERIES:
        errors.append("excel_plots must not include OpAmp series")
    for part in ("rs1g97", "rs1g126", "rs1gt34"):
        m = load_product_model(part)
        if m is None:
            errors.append(f"{part} product_model missing for excel lock")
            continue
        if el.workbook_policy(m) != el.WORKBOOK_POLICY:
            errors.append(
                f"{part} workbook_policy.golden_auto must be {el.WORKBOOK_POLICY}, got {el.workbook_policy(m)!r}"
            )
        if el.ultimate_manual_policy(m) != el.ULTIMATE_POLICY:
            errors.append(
                f"{part} workbook_policy.ultimate_manual must be {el.ULTIMATE_POLICY}, got {el.ultimate_manual_policy(m)!r}"
            )
        if el.pretty_policy(m) != el.PRETTY_POLICY:
            errors.append(
                f"{part} workbook_policy.pretty must be {el.PRETTY_POLICY} (never auto), got {el.pretty_policy(m)!r}"
            )
        if not el.uses_excel_lock(m):
            errors.append(f"{part} must bind excel_plots + workbook_policy")
        errors.extend(el.binding_errors(m, list(enabled_tests_for_part(part) or [])))
    m08 = load_product_model("rs1g08")
    if m08 is not None and el.uses_excel_lock(m08):
        errors.append("rs1g08 must keep sheet_map paste.values (no Path B excel_lock)")
    m07 = load_product_model("rs1g07")
    if m07 is not None and el.uses_excel_lock(m07):
        errors.append("rs1g07 must keep sheet_map paste.values (no Path B excel_lock)")
    m34 = load_product_model("rs1gt34")
    if m34 is not None:
        if el.excel_plots_status(m34).upper() not in ("", "CONFIRMED"):
            errors.append("rs1gt34 excel_plots.status must be CONFIRMED")
        stripped = replace(
            m34, excel_plots={"status": "CONFIRMED", "series": ["vih_vs_vcc"]}
        )
        miss = el.binding_errors(
            stripped,
            list(enabled_tests_for_part("rs1gt34") or []),
            series_data={"icc_vs_vcc", "vih_vs_vcc"},
        )
        if not any("icc_vs_vcc" in e for e in miss):
            errors.append(
                "binding_errors must FAIL when series data has no excel_plots binding"
            )
        illegal = replace(
            m34,
            excel_plots={
                "status": "CONFIRMED",
                "series": [
                    "vih_vs_vcc",
                    "vil_vs_vcc",
                    "icc_vs_vcc",
                    "ii_vs_vcc",
                    "voh_at_ioh",
                    "vol_at_iol",
                    "ioz_vs_vcc",
                    "delta_icc_vs_vcc",
                ],
            },
        )
        en34 = list(enabled_tests_for_part("rs1gt34") or [])
        bad = el.binding_errors(illegal, en34)
        if not any("ioz" in e for e in bad):
            errors.append("ioz_vs_vcc on oe=none must FAIL")
        no_delta = [x for x in en34 if str(x).strip().lower() != "delta_icc"]
        bad_d = el.binding_errors(illegal, no_delta)
        if not any("delta_icc" in e for e in bad_d):
            errors.append("delta_icc_vs_vcc when not enabled must FAIL")
    m97 = load_product_model("rs1g97")
    if m97 is not None:
        bound = el.bound_series_ids(m97)
        if "ioz_vs_vcc" in bound:
            errors.append("rs1g97 excel_plots must not bind ioz (oe none)")
        if "vih_vs_vcc" in bound or "vil_vs_vcc" in bound:
            errors.append("rs1g97 Schmitt must bind vtplus/vtminus not VIH/VIL")
        for need in ("vtplus_vs_vcc", "vtminus_vs_vcc", "dvt_vs_vcc", "delta_icc_vs_vcc"):
            if need not in bound:
                errors.append(f"rs1g97 excel_plots missing {need}")
    m126 = load_product_model("rs1g126")
    if m126 is not None:
        bound = el.bound_series_ids(m126)
        if "ioz_vs_vcc" not in bound:
            errors.append("rs1g126 excel_plots must bind ioz_vs_vcc (OE on card)")
        if "vtplus_vs_vcc" in bound:
            errors.append("rs1g126 is not Schmitt")
    tmp = Path(tempfile.mkdtemp(prefix="ate_excel_lock_"))
    try:
        class _Ctx:
            def __init__(self, root: Path):
                self._root = root
                self.model = "RS1GT34"
                self.package = "SOT23-5"
                self.part_key = "rs1gt34"
                self.sample_size = 1
                (root / "workbook").mkdir(parents=True, exist_ok=True)
                (root / "_manifest").mkdir(parents=True, exist_ok=True)

            def workbook_dir(self):
                return self._root / "workbook"

            def manifest_dir(self):
                return self._root / "_manifest"

            def lab_report_path(self):
                return self.workbook_dir() / f"{self.model}_Lab_Report_{self.package}.xlsx"

            def load_sheet_map(self):
                return {}

            def sessions_dir(self):
                p = self._root / "sessions"
                p.mkdir(parents=True, exist_ok=True)
                return p

        ctx = _Ctx(tmp)
        m = load_product_model("rs1gt34")
        report = {
            "steps": [
                {
                    "test_id": "input_threshold",
                    "dut": 1,
                    "data": {
                        "rows": [
                            {
                                "VCC": 2.0,
                                "PIN": "A",
                                "VIH": 1.2,
                                "VIL": 0.2,
                                "VIH_min_V": 1.0,
                                "VIL_max_V": 0.3,
                            },
                            {
                                "VCC": 3.3,
                                "PIN": "A",
                                "VIH": 1.7,
                                "VIL": 0.4,
                                "VIH_min_V": 1.5,
                                "VIL_max_V": 0.55,
                            },
                        ]
                    },
                },
                {
                    "test_id": "icc",
                    "dut": 1,
                    "data": {
                        "rows": [
                            {"VCC": 2.0, "ICC_uA": 0.4, "IN_A": "L"},
                            {"VCC": 3.3, "ICC_uA": 0.5, "IN_A": "H"},
                        ]
                    },
                },
                {
                    "test_id": "voh",
                    "dut": 1,
                    "data": {
                        "rows": [
                            {
                                "id": "VOH_2p0V_100uA",
                                "VCC": 2.0,
                                "IOH_A": 0.0001,
                                "Measured": 1.95,
                                "Spec_min": 1.9,
                                "pass_mode": "min_only",
                            },
                            {
                                "id": "VOH_3p3V_100uA",
                                "VCC": 3.3,
                                "IOH_A": 0.0001,
                                "Measured": 3.1,
                                "Spec_min": 2.9,
                                "pass_mode": "min_only",
                            },
                        ]
                    },
                },
            ]
        }
        first = el.write_path_b_workbook(ctx=ctx, model=m, report=report)
        dest = Path(first["excel"])
        names1 = sorted(p.name for p in el.list_xlsx(ctx.workbook_dir()))
        if len(names1) != 1:
            errors.append(f"Path B SIM must write one xlsx, got {names1}")
        csv_list = [str(p) for p in (first.get("csv") or [])]
        if not csv_list:
            errors.append("Path B SIM must write sessions/csv sidecars")
        else:
            missing_csv = [p for p in csv_list if not Path(p).is_file()]
            if missing_csv:
                errors.append(f"Path B SIM csv missing on disk: {missing_csv}")
            if any(el.is_ultimate_path(p) for p in csv_list):
                errors.append("CSV must not target pretty/ultimate")
            vth_csv = next((p for p in csv_list if Path(p).stem.upper() == "VTH"), None)
            if vth_csv:
                blob_csv = Path(vth_csv).read_text(encoding="utf-8")
                if "VIH" not in blob_csv or "VCC" not in blob_csv:
                    errors.append("VTH.csv must keep runner headers (no invented columns)")
        logp = str(first.get("session_log") or "")
        if not logp or not Path(logp).is_file():
            errors.append("Path B SIM must write sessions/path_b_write.json")
        else:
            log_txt = Path(logp).read_text(encoding="utf-8")
            if "golden_auto" not in log_txt or "never_auto_write" not in log_txt:
                errors.append("path_b_write.json must bind golden_auto / pretty never auto")
            if el.is_ultimate_path(logp):
                errors.append("session fill log must not land under pretty/ultimate")
        csv1 = Path(first.get("datapoints_csv") or "")
        if not csv1.is_file():
            errors.append("golden_auto write must sidecar full datapoints CSV")
        else:
            body = csv1.read_text(encoding="utf-8")
            if "VIH" not in body or "ICC_uA" not in body:
                errors.append("datapoints CSV must keep full session rows (VIH/ICC_uA)")
            if csv1.resolve() != el.datapoints_csv_path(dest).resolve():
                errors.append(f"datapoints CSV must sit beside golden_auto, got {csv1}")
            if el.is_ultimate_path(csv1):
                errors.append("datapoints CSV must not target pretty/ultimate")
        if int(first.get("plots") or 0) < 1:
            errors.append("Path B SIM must auto-plot when series data exists")
        second = el.write_path_b_workbook(ctx=ctx, model=m, report=report)
        names2 = sorted(p.name for p in el.list_xlsx(ctx.workbook_dir()))
        if len(names2) != 1 or Path(second["excel"]).resolve() != dest.resolve():
            errors.append(f"Path B overwrite must reuse the same xlsx, got {names2}")
        if logp and str(second.get("session_log") or "") and Path(second["session_log"]).resolve() != Path(logp).resolve():
            errors.append("session fill log must overwrite in place")
        csv2 = [Path(p).name for p in (second.get("csv") or [])]
        csv1 = [Path(p).name for p in csv_list]
        if csv_list and csv2 != csv1:
            errors.append(f"CSV overwrite must reuse the same sidecars, got {csv2}")
        fill = fill_workbook_from_report(report=report, ctx=ctx)
        if fill.get("status") == "orphan":
            errors.append(f"fill_workbook Path B SIM orphan: {fill}")
        names3 = sorted(p.name for p in el.list_xlsx(ctx.workbook_dir()))
        if len(names3) != 1:
            errors.append(f"fill_workbook Path B must not create a second book, got {names3}")
        if any(n.endswith("_filled.xlsx") for n in names3):
            errors.append("Path B must not create _filled.xlsx")
        from openpyxl import Workbook as _WB

        orphan_path = ctx.workbook_dir() / "orphan_second.xlsx"
        extra = _WB()
        extra.save(orphan_path)
        extra.close()
        try:
            el.write_path_b_workbook(ctx=ctx, model=m, report=report)
            errors.append("write_path_b_workbook must FAIL when a second xlsx exists")
        except el.OrphanWorkbook:
            pass
        except Exception as exc:
            errors.append(
                f"second xlsx must raise OrphanWorkbook, got {type(exc).__name__}: {exc}"
            )
        fill2 = fill_workbook_from_report(report=report, ctx=ctx)
        if fill2.get("status") != "orphan":
            errors.append(
                f"fill_workbook must status=orphan when a second xlsx exists, got {fill2}"
            )
        orphan_path.unlink(missing_ok=True)
        found = el.detect_series_from_headers(
            ["VCC", "VIH", "VIL", "VIH_min_V", "VIL_max_V"], "VTH"
        )
        if "vih_vs_vcc" not in found or "vil_vs_vcc" not in found:
            errors.append(f"header regex must detect vih/vil, got {found}")
        delta = el.detect_series_from_headers(["VCC", "ICC_uA", "NEAR_PIN"], "DeltaICC")
        if "icc_vs_vcc" in delta or "delta_icc_vs_vcc" not in delta:
            errors.append(f"DeltaICC ICC_uA must map to delta_icc_vs_vcc, got {delta}")
        voh = el.detect_series_from_headers(
            ["VCC", "IOH_A", "Measured", "Spec_min"], "VOH"
        )
        if "voh_at_ioh" not in voh or "vol_at_iol" in voh:
            errors.append(f"VOH Measured must not bind vol_at_iol, got {voh}")
        bad = el.invented_headers(["G16", "GBW_MHz", "VIH"])
        if "G16" not in bad or "GBW_MHz" not in bad or "VIH" in bad:
            errors.append(f"invented_headers must FAIL G16/GBW only, got {bad}")
        if el.header_allowed("G16") or el.header_allowed("GBW_MHz"):
            errors.append("header_allowed must reject invented G16/GBW columns")
        if not el.is_ultimate_path(Path("ultimate_manual.xlsx")):
            errors.append("is_ultimate_path must match filename-only ultimate_manual.xlsx")
        if not el.is_ultimate_path(Path("pretty.xlsx")):
            errors.append("is_ultimate_path must match filename-only pretty.xlsx")
        if not el.is_ultimate_path("jot_book.xlsx") or not el.is_ultimate_path("all-test.xlsx"):
            errors.append("is_ultimate_path must match jot / all-test filename tokens")
        if el.is_ultimate_path(Path("RS1GT34_Lab_Report_SOT23-5.xlsx")):
            errors.append("is_ultimate_path must not flag golden Lab_Report")
        jot = ctx.workbook_dir() / "ultimate_manual.xlsx"
        extra = _WB()
        extra.save(jot)
        extra.close()
        names_g = sorted(p.name for p in el.golden_xlsx(ctx.workbook_dir()))
        if any(el.is_ultimate_path(Path(n)) for n in names_g):
            errors.append("golden_xlsx must exclude ultimate_manual")
        if jot.name in names_g:
            errors.append("golden_xlsx listed ultimate_manual as a Version book")
        third = el.write_path_b_workbook(ctx=ctx, model=m, report=report)
        if el.is_ultimate_path(third["excel"]):
            errors.append("golden_auto write must not target ultimate_manual")
        if Path(third["excel"]).resolve() == jot.resolve():
            errors.append("auto write path == ultimate")
        fill3 = fill_workbook_from_report(report=report, ctx=ctx)
        if fill3.get("status") == "ultimate":
            errors.append(f"fill_workbook must not treat jot as dest when golden exists, got {fill3}")
        if el.is_ultimate_path(str(fill3.get("excel") or "")):
            errors.append("fill_workbook Path B must not write ultimate_manual")
        names4 = sorted(p.name for p in el.golden_xlsx(ctx.workbook_dir()))
        if len(names4) != 1:
            errors.append(f"jot beside golden must not become a second Version book, got {names4}")
        try:
            el.coerce_golden_auto_lab_report(ctx, str(jot))
            errors.append("coerce_golden_auto_lab_report must FAIL when proposed path is ultimate")
        except el.UltimateWorkbook:
            pass
        except Exception as exc:
            errors.append(
                f"ultimate proposed path must raise UltimateWorkbook, got {type(exc).__name__}: {exc}"
            )
        pretty = ctx.workbook_dir() / "pretty.xlsx"
        extra_p = _WB()
        extra_p.save(pretty)
        extra_p.close()
        if pretty.name in [p.name for p in el.golden_xlsx(ctx.workbook_dir())]:
            errors.append("golden_xlsx must exclude pretty (never auto)")
        fourth = el.write_path_b_workbook(ctx=ctx, model=m, report=report)
        if el.is_ultimate_path(third["excel"]) or el.is_ultimate_path(fourth["excel"]):
            errors.append("auto write must not target pretty/ultimate")
        if Path(fourth["excel"]).resolve() == pretty.resolve():
            errors.append("auto write path == pretty")
        try:
            el.write_path_b_csv(
                ctx=ctx,
                model=m,
                report=report,
                grouped={"VTH": ["input_threshold"]},
                dest_xlsx=pretty,
            )
            errors.append("write_path_b_csv must FAIL when dest is pretty")
        except el.UltimateWorkbook:
            pass
        except Exception as exc:
            errors.append(
                f"pretty CSV dest must raise UltimateWorkbook, got {type(exc).__name__}: {exc}"
            )
        pretty_csv = el.datapoints_csv_path(pretty)
        if pretty_csv.is_file():
            errors.append("pretty book must not get an auto datapoints CSV")
        fourth_pts = Path(fourth.get("datapoints_csv") or "")
        if fourth_pts.is_file() and el.is_ultimate_path(fourth_pts):
            errors.append("datapoints CSV must not target pretty/ultimate")
        class _SheetCtx:
            def __init__(self, inner):
                self._inner = inner
                self.model = inner.model
                self.package = inner.package
                self.part_key = inner.part_key
                self.sample_size = inner.sample_size
            def workbook_dir(self):
                return ctx.workbook_dir()
            def manifest_dir(self):
                return ctx.manifest_dir()
            def lab_report_path(self):
                return ctx.lab_report_path()
            def load_sheet_map(self):
                return {"workbook": {"path": "../workbook/ultimate_manual.xlsx"}}
        mapped = _SheetCtx(ctx)
        dest_mapped = el.canonical_workbook_path(mapped, m)
        if el.is_ultimate_path(dest_mapped):
            errors.append("sheet_map ultimate path must not become golden_auto dest")
        bound = el.bind_golden_auto(ctx, m)
        if not bound or el.is_ultimate_path(bound):
            errors.append("bind_golden_auto must return Version golden, not ultimate")
    except Exception as exc:
        errors.append(f"excel lock SIM: {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return errors


_DRAFT_GATE_SKUS = (
    "rs1g08",
    "rs1g07",
    "rs1g14",
    "rs1g32",
    "rs1gt08",
    "rs1gt32",
    "rs1g125",
)
_DRAFT_SCAFFOLD_SKUS = _DRAFT_GATE_SKUS + ("rs164",)

_G14_VT = {
    1.65: {"VT_plus": [0.75, 1.05], "VT_minus": [0.3, 0.6]},
    2.3: {"VT_plus": [1.25, 1.55], "VT_minus": [0.35, 0.65]},
    3.0: {"VT_plus": [1.5, 2.1], "VT_minus": [0.45, 0.75]},
    4.5: {"VT_plus": [2.3, 3.0], "VT_minus": [0.7, 1.0]},
    5.5: {"VT_plus": [2.8, 3.4], "VT_minus": [0.85, 1.15]},
}


def _recipe_search_ok(part: str, m) -> list[str]:
    errors: list[str] = []
    search = (m.recipe or {}).get("search") if isinstance(m.recipe, dict) else {}
    if not isinstance(search, dict) or not search:
        return [f"{part} recipe.search missing (gate SKU; PROPOSED_FROM_LIVE)"]
    st = str(search.get("status") or "")
    if "PROPOSED" not in st.upper():
        errors.append(f"{part} recipe.search.status must stay PROPOSED_FROM_LIVE, got {st!r}")
    if not isinstance(search.get("vih"), dict) or not isinstance(search.get("vil"), dict):
        errors.append(f"{part} recipe.search must have vih/vil stages")
    ladder = search.get("step_ladder_V") or search.get("step_ladder")
    if not isinstance(ladder, list) or not ladder:
        errors.append(f"{part} recipe.search step_ladder_V missing")
    on_hit = search.get("on_hit") if isinstance(search.get("on_hit"), dict) else {}
    if not on_hit.get("skip_rest_of_walk"):
        errors.append(f"{part} recipe.search on_hit.skip_rest_of_walk must be true")
    return errors


def _unsigned_draft_ok(part: str, m) -> list[str]:
    """DRAFT SKUs stay UNCONFIRMED. Do not call _fail_closed_until_signed (that FAILs the suite)."""
    errors: list[str] = []
    for name, st in (
        ("status", m.status),
        ("truth_table", m.truth_table_status),
        ("isolation", m.isolation_status),
    ):
        if is_datasheet_signed(st):
            errors.append(
                f"{part} {name}={st!r} must stay UNCONFIRMED (no number unlock overnight)"
            )
        elif name != "isolation" and not is_unconfirmed_status(st):
            # isolation N_A on sequential is allowed
            if str(st or "").strip().upper() not in ("N_A", "NA", "N/A"):
                errors.append(f"{part} {name}={st!r} must be UNCONFIRMED")
    if vcc_grid_unconfirmed(m) is False and (m.vcc_grid or {}).get("status"):
        gst = str((m.vcc_grid or {}).get("status") or "")
        if is_datasheet_signed(gst):
            errors.append(f"{part} vcc_grid.status must stay UNCONFIRMED, got {gst!r}")
    return errors


def _draft_scaffold_ok() -> list[str]:
    """Overnight Path B DRAFT scaffold. Physics FAIL bars. Numbers stay UNCONFIRMED."""
    from ate.tests.logic import logic_dc as ldc

    errors: list[str] = []
    for part in _DRAFT_SCAFFOLD_SKUS:
        if not has_product_model(part):
            errors.append(f"{part} product_model missing (DRAFT scaffold)")
    m08 = load_product_model("rs1g08")
    m07 = load_product_model("rs1g07")
    m14 = load_product_model("rs1g14")
    m32 = load_product_model("rs1g32")
    mgt08 = load_product_model("rs1gt08")
    mgt32 = load_product_model("rs1gt32")
    m125 = load_product_model("rs1g125")
    m164 = load_product_model("rs164")
    if None in (m08, m07, m14, m32, mgt08, mgt32, m125, m164):
        return errors + ["DRAFT scaffold: one or more product_model failed to load"]

    yaml08 = load_part_yaml("rs1g08")
    if str(yaml08.get("package") or "") != "SOT23":
        errors.append(f"rs1g08 campaign package must stay SOT23, got {yaml08.get('package')!r}")
    a_drive = m08.pin_drive.get("A")
    b_drive = m08.pin_drive.get("B")
    if a_drive is None or a_drive.src != "awg" or a_drive.ch != 1:
        errors.append("rs1g08 pin_drive A must stay AWG CH1")
    if b_drive is None or b_drive.src != "awg" or b_drive.ch != 2:
        errors.append("rs1g08 pin_drive B must stay AWG CH2")
    from ate.tests.logic import excel_lock as el

    if el.uses_excel_lock(m08):
        errors.append("rs1g08 must keep sheet_map paste.values (no Path B excel_lock)")

    for part, m in (
        ("rs1g08", m08),
        ("rs1g07", m07),
        ("rs1g14", m14),
        ("rs1g32", m32),
        ("rs1gt08", mgt08),
        ("rs1gt32", mgt32),
        ("rs1g125", m125),
        ("rs164", m164),
    ):
        errors += _unsigned_draft_ok(part, m)

    for part in _DRAFT_GATE_SKUS:
        m = load_product_model(part)
        if m is None:
            continue
        errors += _recipe_search_ok(part, m)

    # G08 AND-2 other=H; no IOZ
    en08 = set(enabled_tests_for_part("rs1g08") or [])
    if "ioz" in en08:
        errors.append("rs1g08 enabled_tests must not include ioz")
    if m08.has_oe():
        errors.append("rs1g08 oe must be none")
    a08 = isolation_for(m08, "A") or derive_isolation(
        logic_inputs=m08.logic_inputs, truth_table=m08.truth_table, output_pin=m08.output_pin
    ).get("A") or []
    b08 = isolation_for(m08, "B") or []
    if not any(p.fix.get("B") == "H" and p.y_expect == "track" for p in a08):
        errors.append("rs1g08 AND isolation A must track with B=H")
    if not any(p.fix.get("A") == "H" and p.y_expect == "track" for p in b08):
        errors.append("rs1g08 AND isolation B must track with A=H")
    rec08 = m08.recipe or {}
    try:
        if abs(float(rec08.get("delta_offset_v")) - 0.6) > 1e-9:
            errors.append(f"rs1g08 recipe.delta_offset_v must stay 0.6, got {rec08.get('delta_offset_v')}")
    except (TypeError, ValueError):
        errors.append("rs1g08 recipe.delta_offset_v must stay 0.6 (CMOS ICCT)")
    force08 = ldc._delta_force_v(m08, 5.5)
    if abs(float(force08) - 4.9) > 1e-9:
        errors.append(f"rs1g08 CMOS delta_icc force must be VCC-0.6=4.9, got {force08}")

    # G07 OD: disable VOH; Y=Z != IOZ
    if not is_open_drain(m07):
        errors.append("rs1g07 output_type must be open_drain")
    if m07.has_oe():
        errors.append("rs1g07 oe must be none (Y=Z is not OE IOZ)")
    en07 = set(enabled_tests_for_part("rs1g07") or [])
    if "voh" in en07:
        errors.append("rs1g07 must not enable voh (open-drain)")
    if "ioz" in en07:
        errors.append("rs1g07 must not enable ioz (Y=Z is not IOZ)")
    if "vol" not in en07:
        errors.append("rs1g07 enabled_tests missing vol (extract-explicit IOL rows)")
    yaml07 = load_part_yaml("rs1g07")
    vol07 = yaml07.get("vol_table") if isinstance(yaml07.get("vol_table"), list) else []
    if len(vol07) != 4:
        errors.append(f"rs1g07 vol_table must be 4 extract-explicit IOL rows, got {len(vol07)}")
    for row in vol07:
        if not isinstance(row, dict):
            continue
        iol = abs(float(row.get("iol_a") or 0))
        if iol <= 0.0002:
            errors.append("rs1g07 must not invent 100uA VOL (light-load current glyph-missing)")
        sid = str(row.get("id") or "")
        if "24mA" in sid or "24ma" in sid.lower():
            errors.append("rs1g07 must not invent IOL 24mA VCC (glyph-missing)")
    yz = [r for r in m07.truth_table if r.get("A") == "H" and r.get("Y") == "Z"]
    if not yz:
        errors.append("rs1g07 truth_table must have A=H -> Y=Z (open-drain OFF)")
    try:
        ldc._run_voh_path_b(None, _params(part="rs1g07", vcc=5.0))
        errors.append("Verify FAIL bar: voh on open-drain rs1g07 must raise")
    except RuntimeError as exc:
        if "open-drain" not in str(exc).lower():
            errors.append(f"voh rs1g07 must say open-drain, got {exc!r}")
    except Exception as exc:
        errors.append(f"voh rs1g07 must raise RuntimeError, got {type(exc).__name__}: {exc}")
    try:
        ldc._run_ioz(None, _params(part="rs1g07", vcc=5.0))
        errors.append("Verify FAIL bar: ioz on rs1g07 (Y=Z != IOZ) must raise")
    except RuntimeError as exc:
        if "not applicable" not in str(exc).lower() and "oe is none" not in str(exc).lower():
            errors.append(f"ioz rs1g07 should say not applicable, got {exc!r}")
    except Exception as exc:
        errors.append(f"ioz rs1g07 must raise RuntimeError, got {type(exc).__name__}: {exc}")

    # G14 Schmitt VT+/- range
    if not m14.schmitt:
        errors.append("rs1g14 schmitt must be true")
    if lookup_pass_mode(m14, "VTPLUS_V", "vth") != "range":
        errors.append("rs1g14 VT+ pass_mode must be range")
    if lookup_pass_mode(m14, "VTMINUS_V", "vth") != "range":
        errors.append("rs1g14 VT- pass_mode must be range")
    grid14 = m14.vcc_grid or {}
    if str(grid14.get("kind") or "") != "schmitt_VT":
        errors.append(f"rs1g14 vcc_grid.kind must be schmitt_VT, got {grid14.get('kind')!r}")
    got_vt: dict[float, dict[str, Any]] = {}
    for pt in grid14.get("fixed_points") or []:
        if not isinstance(pt, dict) or pt.get("vcc") is None:
            continue
        got_vt[round(float(pt["vcc"]), 6)] = pt
    for vcc, want in _G14_VT.items():
        pt = got_vt.get(round(float(vcc), 6))
        if pt is None:
            errors.append(f"rs1g14 VT grid missing vcc={vcc}")
            continue
        plus = pt.get("VT_plus") or pt.get("VT+")
        minus = pt.get("VT_minus") or pt.get("VT-")
        if list(plus or []) != want["VT_plus"]:
            errors.append(f"rs1g14 VT+ @ {vcc} must be {want['VT_plus']}, got {plus}")
        if list(minus or []) != want["VT_minus"]:
            errors.append(f"rs1g14 VT- @ {vcc} must be {want['VT_minus']}, got {minus}")
    a14 = isolation_for(m14, "A")
    if not any(p.y_expect == "invert" for p in a14):
        errors.append("rs1g14 isolation A must invert (Y=NOT A)")
    en14 = set(enabled_tests_for_part("rs1g14") or [])
    if "voh" in en14 or "vol" in en14:
        errors.append("rs1g14 must not enable voh/vol without table rows")

    # G32 OR-2 other=L
    a32 = isolation_for(m32, "A")
    b32 = isolation_for(m32, "B")
    if not any(p.fix.get("B") == "L" and p.y_expect == "track" for p in a32):
        errors.append("rs1g32 OR isolation A must track with B=L")
    if not any(p.fix.get("A") == "L" and p.y_expect == "track" for p in b32):
        errors.append("rs1g32 OR isolation B must track with A=L")
    highs32 = vectors_for_output(m32, "H")
    if not any(v.get("A") == "L" and v.get("B") == "H" for v in highs32):
        errors.append("rs1g32 OR Y=H must include A=L B=H")

    # GT08 / GT32 TTL 2.0-5.5; ICCT 3.4 not 0.6
    for part, m, other in (("rs1gt08", mgt08, "H"), ("rs1gt32", mgt32, "L")):
        if round(float(m.vcc_op_min or 0), 6) != 2.0 or round(float(m.vcc_op_max or 0), 6) != 5.5:
            errors.append(f"{part} TTL VCC op must be 2.0-5.5, got {m.vcc_op_min}..{m.vcc_op_max}")
        merged = [round(float(x), 6) for x in m.vcc_list]
        if any(v < 2.0 - 1e-9 for v in merged):
            errors.append(f"{part} TTL vcc_list must not include <2.0, got {merged}")
        if 1.65 in merged:
            errors.append(f"{part} TTL must not sweep CMOS 1.65")
        if 2.0 not in merged or 3.3 not in merged:
            errors.append(f"{part} TTL merged vcc_list must include 2.0 and 3.3")
        force = ldc._delta_force_v(m, 5.5)
        if abs(float(force) - 3.4) > 1e-9:
            errors.append(f"{part} ICCT force must be one_in 3.4, got {force}")
        if abs(float(force) - 4.9) < 1e-9:
            errors.append(f"Verify FAIL bar: {part} must not invent VCC-0.6")
        hold = "B" if other == "H" else "B"
        pats = isolation_for(m, "A")
        if not any(p.fix.get("B") == other and p.y_expect == "track" for p in pats):
            errors.append(f"{part} isolation A must track with B={other}")
        rec = m.recipe or {}
        if rec.get("delta_offset_v") is not None:
            errors.append(f"{part} must not invent recipe.delta_offset_v (TTL ICCT uses 3.4)")

    # G125 OE active-L -> IOZ ON (opposite of 126 active-H)
    if not m125.has_oe() or m125.oe_mode != "low":
        errors.append("rs1g125 oe must be active low")
    en125 = set(enabled_tests_for_part("rs1g125") or [])
    if "ioz" not in en125:
        errors.append("rs1g125 enabled_tests must include ioz (OE active-L)")
    if "voh" in en125 or "vol" in en125:
        errors.append("rs1g125 must not enable voh/vol without table rows")
    a125 = isolation_for(m125, "A")
    if not any(p.fix.get("OE") == "L" and p.y_expect == "track" for p in a125):
        errors.append("rs1g125 isolation A must hold OE=L (active-L)")
    zrow = [r for r in m125.truth_table if r.get("OE") == "H" and r.get("Y") == "Z"]
    if not zrow:
        errors.append("rs1g125 truth_table must have OE=H -> Y=Z")
    if m125.oe_inactive_level() != "H":
        errors.append("rs1g125 OE inactive must be H (active-L)")
    when125 = str((m125.recipe or {}).get("ioz_when") or "").lower().replace("-", "_")
    if "inactive" not in when125:
        errors.append("rs1g125 recipe.ioz_when must be oe_inactive (IOZ when OE inactive only)")
    try:
        vec125 = ioz_force_vector(m125)
    except Exception as exc:
        errors.append(f"rs1g125 ioz_force_vector: {exc}")
        vec125 = {}
    if vec125.get("OE") != "H":
        errors.append(f"G125 ioz must force OE inactive H only, got {vec125}")
    if vec125.get("OE") == "L":
        errors.append("Verify FAIL bar: G125 ioz must not force OE active L")
    src_ioz = inspect.getsource(ldc._run_ioz)
    if "ioz_force_vector" not in src_ioz:
        errors.append("logic_dc _run_ioz must use ioz_force_vector (OE inactive only)")
    if "oe_active_level" in src_ioz:
        errors.append("logic_dc _run_ioz must not force OE active")

    # RS164 sequential -- NOT gate 2^n
    if not is_sequential(m164):
        errors.append("rs164 product_class/recipe.runner must be sequential_shift_register")
    en164 = {str(x).strip().lower() for x in (enabled_tests_for_part("rs164") or [])}
    for banned in ("icc", "delta_icc", "input_threshold", "vth", "voh", "vol", "ioz"):
        if banned in en164:
            errors.append(f"rs164 must not enable Path B {banned} (not combinational 2^n)")
    plan = sim_icc_plan(m164)
    if int(plan.get("n") or 0) == 16:
        errors.append("Verify FAIL bar: rs164 ICC must not be gate 2^4=16")
    if int(plan.get("n") or 0) != 0:
        errors.append(f"rs164 sim_icc_plan n must be 0 (not combinational), got {plan}")
    n_inputs = len(m164.logic_inputs)
    if n_inputs and int(plan.get("n") or 0) == (1 << n_inputs):
        errors.append(f"rs164 ICC must not be 2^{n_inputs}={1 << n_inputs}")
    try:
        ldc._run_icc(None, _params(part="rs164", vcc=5.0))
        errors.append("Verify FAIL bar: icc on sequential rs164 must raise")
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "sequential" not in msg and "2^n" not in msg and "2n" not in msg:
            errors.append(f"icc rs164 must say sequential / not 2^n, got {exc!r}")
    except Exception as exc:
        errors.append(f"icc rs164 must raise RuntimeError, got {type(exc).__name__}: {exc}")
    try:
        ldc._run_delta_icc(None, _params(part="rs164", vcc=5.0))
        errors.append("Verify FAIL bar: delta_icc on sequential rs164 must raise")
    except RuntimeError as exc:
        if "sequential" not in str(exc).lower() and "2^n" not in str(exc).lower():
            errors.append(f"delta_icc rs164 must say sequential, got {exc!r}")
    except Exception as exc:
        errors.append(f"delta_icc rs164 must raise RuntimeError, got {type(exc).__name__}: {exc}")
    dc164 = m164.dc_limits if isinstance(m164.dc_limits, dict) else {}
    icct164 = dc164.get("ICCT_uA") if isinstance(dc164.get("ICCT_uA"), dict) else {}
    if str(icct164.get("status") or "").strip().upper() != "ABSENT":
        errors.append(f"rs164 ICCT_uA.status must be ABSENT, got {icct164.get('status')!r}")
    runner = str((m164.recipe or {}).get("runner") or "")
    if "sequential" not in runner.lower():
        errors.append(f"rs164 recipe.runner must be sequential_shift_register, got {runner!r}")

    src_ldc = _LOGIC_DC.read_text(encoding="utf-8")
    src_model = _MODEL.read_text(encoding="utf-8")
    if "is_open_drain" not in src_ldc or "is_sequential" not in src_ldc:
        errors.append("logic_dc.py must fail-close open-drain VOH / sequential ICC via generic flags")
    if "is_open_drain" not in src_model or "is_sequential" not in src_model:
        errors.append("product_model.py must expose is_open_drain / is_sequential (no part-name ifs)")
    return errors


def _schmitt_has_vt_split(m) -> bool:
    pm = m.pass_mode or {}
    for key in pm:
        token = str(key).upper().replace("+", "PLUS").replace("-", "MINUS").replace("_", "")
        if "VTPLUS" in token or "VTMINUS" in token or token in ("HYST", "HYSTERESIS", "DVT"):
            return True
    grid = m.vcc_grid or {}
    return str(grid.get("kind") or "") == "schmitt_VT"


def _physics_fail_bars_ok() -> list[str]:
    """Generic SIM: OD+voh, sequential 2^n, Schmitt VIH collapse, G125 ioz inactive."""
    errors: list[str] = []
    for path in sorted(PARTS_DIR.glob("*.yaml")):
        part = path.stem.lower()
        if not has_product_model(part):
            continue
        m = load_product_model(part)
        if m is None:
            continue
        en = {str(x).strip().lower() for x in (enabled_tests_for_part(part) or [])}
        if is_open_drain(m) and "voh" in en:
            errors.append(f"{part}: open_drain + voh enabled -> FAIL")
        if is_sequential(m):
            if "icc" in en or "delta_icc" in en:
                errors.append(f"{part}: sequential + icc enabled -> FAIL")
            plan = sim_icc_plan(m)
            n = int(plan.get("n") or 0)
            n_in = len(m.logic_inputs)
            if n_in and n == (1 << n_in):
                errors.append(f"{part}: sequential + icc 2^{n_in}={1 << n_in} -> FAIL")
            if n != 0:
                errors.append(f"{part}: sequential sim_icc_plan n must be 0 (not 2^n), got {n}")
        if m.schmitt:
            it = str((m.pass_mode or {}).get("input_threshold") or "").lower().replace("-", "_")
            if it in ("range", "min_only", "max_only") and not _schmitt_has_vt_split(m):
                errors.append(f"{part}: schmitt collapsing to single VIH / input_threshold:{it}")
            if not _schmitt_has_vt_split(m):
                errors.append(f"{part}: schmitt must keep VT+/VT- (must not collapse to single VIH)")
    return errors


def _sts_latest_ok() -> list[str]:
    """Version-root report.pdf overwrite from session rows. Never invent pass numbers."""
    from ate.reporting.sts_datalog import export_latest_report

    errors: list[str] = []
    datalog_src = Path(__file__).resolve().parents[1] / "core" / "datalog.py"
    if "export_latest_report" not in datalog_src.read_text(encoding="utf-8"):
        errors.append("sync_report_from_session must hook export_latest_report")
    worker_src = Path(__file__).resolve().parents[1] / "worker" / "server.py"
    if "export_latest_report" not in worker_src.read_text(encoding="utf-8"):
        errors.append("export_datalog must hook export_latest_report")
    tmp = Path(tempfile.mkdtemp(prefix="ate_sts_latest_"))
    try:
        version = tmp / "Version_1"
        sessions = version / "sessions"
        doc = {
            "header": {"time": "t", "session_id": "s1"},
            "identity": {"part": "RS1GT34", "operator": "Eugene", "version": "Version_1"},
            "steps": [
                {
                    "test_id": "input_threshold",
                    "dut": 1,
                    "success": False,
                    "measurements": [
                        {
                            "id": "VIH_V",
                            "unit": "V",
                            "min": 1.0,
                            "max": None,
                            "value": 0.4,
                            "result": "fail",
                        }
                    ],
                }
            ],
        }
        export_latest_report(doc, sessions_dir=sessions, version_dir=version)
        latest = version / "report.pdf"
        if not latest.is_file() or not latest.read_bytes().startswith(b"%PDF"):
            errors.append("Version folder latest report.pdf missing after STS export")
        else:
            blob = latest.read_bytes()
            if b"VIH_V" not in blob:
                errors.append("latest report.pdf must copy measured id (never invent)")
            if b"FAIL" not in blob:
                errors.append("latest report.pdf must show FAIL vs limits (not invent PASS)")
            if b"0.4" not in blob:
                errors.append("latest report.pdf must copy measured value (never invent pass numbers)")
        if not (sessions / "datalog.pdf").is_file():
            errors.append("sessions/datalog.pdf must still be written (existing STS path)")
    except Exception as exc:
        errors.append(f"STS latest PDF SIM: {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return errors


def _dual_channel_recipe_ok() -> list[str]:
    """Future 2Gxx Continue flag. No fake 2G YAML. Path B registry stays dual_channel=False."""
    errors: list[str] = []
    fake2g = sorted(PARTS_DIR.glob("rs2g*.yaml"))
    if fake2g:
        errors.append(
            f"must not invent 2G part YAML without Datasheet card, got {[p.name for p in fake2g]}"
        )
    schema_txt = CARD_FIELDS_SCHEMA_PATH.read_text(encoding="utf-8")
    if "recipe.dual_channel_continue" not in schema_txt or "recipe.channels" not in schema_txt:
        errors.append("card_fields.schema.yaml must name recipe.dual_channel_continue / recipe.channels")
    model_src = _MODEL.read_text(encoding="utf-8")
    if "dual_channel_continue" not in model_src or "apply_dual_channel_continue" not in model_src:
        errors.append("product_model must expose dual_channel_continue (OpAmp pattern as DATA)")
    runner_src = Path(__file__).resolve().parents[1] / "core" / "runner.py"
    rtxt = runner_src.read_text(encoding="utf-8")
    if "_apply_part_dual_channel" not in rtxt:
        errors.append("runner must honor recipe.dual_channel_continue (not hardcode OpAmp)")
    for part in ("rs1g97", "rs1g126", "rs1gt34") + _DRAFT_SCAFFOLD_SKUS:
        m = load_product_model(part)
        if m is None:
            continue
        if dual_channel_continue(m):
            errors.append(f"{part} must not set dual_channel_continue without a 2G Datasheet card")
    load_family("logic")
    icc = get("icc")
    if icc is None or icc.dual_channel:
        errors.append("icc must stay registered dual_channel=False")
    fake = SimpleNamespace(recipe={"dual_channel_continue": True, "channels": ["CHA", "CHB"]})
    if not dual_channel_continue(fake):
        errors.append("dual_channel_continue True must enable CHA then CHB")
    if recipe_channels(fake) != ["CHA", "CHB"]:
        errors.append(f"recipe.channels must be CHA then CHB, got {recipe_channels(fake)}")
    if icc is not None:
        over = apply_dual_channel_continue([icc], fake)
        if not over or not getattr(over[0], "dual_channel", False):
            errors.append("apply_dual_channel_continue must OR flag onto Path B spec at run")
        if icc.dual_channel:
            errors.append("apply_dual_channel_continue must not mutate registered spec")
        if over and over[0].run is not icc.run:
            errors.append("apply_dual_channel_continue must not wrap TestSpec.run")
    merged = merge_recipe_channels(fake, ["CHA"])
    if merged != ["CHA", "CHB"]:
        errors.append(f"merge_recipe_channels must expand CHA-only to CHA then CHB, got {merged}")
    off = SimpleNamespace(recipe={})
    if dual_channel_continue(off):
        errors.append("missing dual_channel_continue must stay false")
    doc = Path(__file__).resolve().parents[2] / "docs" / "LOGIC_DC_DUAL_CHANNEL.md"
    if not doc.is_file():
        errors.append("docs/LOGIC_DC_DUAL_CHANNEL.md missing")
    else:
        txt = doc.read_text(encoding="utf-8")
        if "CHA" not in txt or "CHB" not in txt or "Continue" not in txt:
            errors.append("dual-channel doc must name CHA then CHB Continue")
        if "OpAmp" not in txt:
            errors.append("dual-channel doc must say OpAmp pattern reused as DATA")
        if "Datasheet" not in txt:
            errors.append("dual-channel doc must forbid fake 2G YAML without Datasheet card")
    return errors


def check_logic_dc() -> list[str]:
    errors: list[str] = []
    errors += _no_part_name_ifs(_LOGIC_DC)
    errors += _no_part_name_ifs(_MODEL)
    if _THRESHOLD_SEARCH.is_file():
        errors += _no_part_name_ifs(_THRESHOLD_SEARCH)
    else:
        errors.append("ate/tests/logic/threshold_search.py missing")
    if _DC_ALIAS.is_file():
        errors += _no_part_name_ifs(_DC_ALIAS)
    else:
        errors.append("ate/tests/logic/dc.py missing (import-format alias of logic_dc)")
    if 'part.get("logic_dc")' not in _MODEL.read_text(encoding="utf-8"):
        errors.append("product_model loader must accept logic_dc: import-format key")
    if not has_product_model("rs1g08") or not has_product_model("rs1g97"):
        errors.append("rs1g08 and rs1g97 must carry product_model schema")
    errors += _and_isolation_ok()
    errors += _status_tokens_ok()
    errors += _rs1g97_holds()
    errors += _buf126_ok()
    errors += _rs1gt34_ok()
    errors += _threshold_search_ok()
    errors += _enabled_voh_vol_tables_ok()
    errors += _scale_and_overlay_ok()
    errors += _seelim_wrap_ok()
    errors += _registry_ok()
    errors += _runnable_ok()
    errors += _handoff_ok()
    errors += _settle_loop_ok()
    errors += _operator_doc_ok()
    errors += _panel_ok()
    errors += _excel_lock_ok()
    errors += _draft_scaffold_ok()
    errors += _physics_fail_bars_ok()
    errors += _sts_latest_ok()
    errors += _dual_channel_recipe_ok()
    load_family("opamp")
    return errors


def main() -> int:
    errors = check_logic_dc()
    if errors:
        print("FAIL logic-dc Path B:")
        for line in errors:
            print(f"  - {line}")
        return 1
    print(
        "OK logic-dc: shared logic_dc.py + product_model "
        "(Datasheet-signed CONFIRM only; UNCONFIRMED is not greenable)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
