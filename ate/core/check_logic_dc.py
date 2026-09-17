"""Path B Logic DC: shared runner + product_model YAML (not per-chip forks).

Run: python -m ate.core.check_logic_dc
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from ate.core.registry import all_tests, get, load_family
from ate.core.specs import infer_pass_mode, judge_value, load_part_specs
from ate.fixture.modes import enabled_tests_for_part
from ate.tests.logic.product_model import (
    claimed_signed_without_datasheet,
    derive_isolation,
    has_product_model,
    isolation_for,
    isolation_for_run,
    is_datasheet_signed,
    is_unconfirmed_status,
    iter_logic_corners,
    load_part_yaml,
    load_product_model,
    lookup_pass_mode,
    sim_icc_plan,
    vectors_for_output,
)

_LOGIC_DC = Path(__file__).resolve().parents[1] / "tests" / "logic" / "logic_dc.py"
_DC_ALIAS = Path(__file__).resolve().parents[1] / "tests" / "logic" / "dc.py"
_MODEL = Path(__file__).resolve().parents[1] / "tests" / "logic" / "product_model.py"

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


def check_logic_dc() -> list[str]:
    errors: list[str] = []
    errors += _no_part_name_ifs(_LOGIC_DC)
    errors += _no_part_name_ifs(_MODEL)
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
    errors += _scale_and_overlay_ok()
    errors += _seelim_wrap_ok()
    errors += _registry_ok()
    errors += _panel_ok()
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
