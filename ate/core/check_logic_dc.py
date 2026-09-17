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
from ate.core.specs import load_part_specs
from ate.fixture.modes import enabled_tests_for_part
from ate.tests.logic.product_model import (
    derive_isolation,
    has_product_model,
    isolation_for,
    load_product_model,
    vectors_for_output,
)

_LOGIC_DC = Path(__file__).resolve().parents[1] / "tests" / "logic" / "logic_dc.py"
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
    return errors


def _97_isolation_ok() -> list[str]:
    errors: list[str] = []
    m = load_product_model("rs1g97")
    if m is None:
        return ["rs1g97 product_model missing"]
    if m.has_oe():
        errors.append("rs1g97 oe must be none")
    if not m.schmitt:
        errors.append("rs1g97 schmitt must be true (VT+/VT-)")
    en = set(enabled_tests_for_part("rs1g97") or [])
    for banned in ("ioz", "ioff", "ioff_leakage"):
        if banned in en:
            errors.append(f"rs1g97 must not enable {banned}")
    for need in ("input_threshold", "icc", "delta_icc", "ii", "voh", "vol"):
        if need not in en:
            errors.append(f"rs1g97 enabled_tests missing {need}")
    # Datasheet function table (extract page 1): C=L => Y=B; C=H => Y=A AND B.
    # Mux Y=C?A:B is wrong (A=H B=L C=H is Y=L, not H).
    want = {
        ("L", "L", "L", "L"),
        ("H", "L", "L", "L"),
        ("L", "H", "L", "H"),
        ("H", "H", "L", "H"),
        ("L", "L", "H", "L"),
        ("H", "L", "H", "L"),
        ("L", "H", "H", "L"),
        ("H", "H", "H", "H"),
    }
    got = set()
    for row in m.truth_table:
        got.add((row.get("A"), row.get("B"), row.get("C"), row.get("Y")))
    if got != want:
        errors.append(f"rs1g97 truth_table must match datasheet extract, got {sorted(got)}")
    if ("H", "L", "H", "H") in got:
        errors.append("rs1g97 must not use C-select MUX row A=H B=L C=H Y=H")
    a = isolation_for(m, "A")
    b = isolation_for(m, "B")
    c = isolation_for(m, "C")
    if not any(p.fix.get("B") == "H" and p.fix.get("C") == "H" and p.y_expect == "track" for p in a):
        errors.append("rs1g97 isolation A: need B=H C=H track (Y=A AND B)")
    if not any(p.fix.get("A") == "L" and p.fix.get("C") == "L" and p.y_expect == "track" for p in b):
        errors.append("rs1g97 isolation B: need A=L C=L track (Y=B when C=L)")
    if not any(
        p.fix.get("A") == "L" and p.fix.get("B") == "H" and p.y_expect == "invert" for p in c
    ):
        errors.append("rs1g97 isolation C: need A=L B=H invert")
    c_drive = m.pin_drive.get("C")
    if c_drive is None or c_drive.src != "psu" or c_drive.ch != 3:
        errors.append("rs1g97 pin_drive C must be PSU CH3 (CH2 is Y-load/vref)")
    specs = {s.get("id"): s for s in load_part_specs("rs1g97")}
    if specs.get("ICC_uA", {}).get("test") != "icc":
        errors.append("rs1g97 ICC_uA spec test must be icc (Path B id)")
    if str(specs.get("ICC_uA", {}).get("pass_mode") or "") != "max-only":
        errors.append("rs1g97 ICC_uA pass_mode must be max-only")
    if str(specs.get("VTPLUS_V", {}).get("pass_mode") or "") != "range":
        errors.append("rs1g97 VTPLUS_V pass_mode must be range")
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
    # Same runner for AND and 3-input: one TestSpec, data in YAML
    from ate.tests.logic import logic_dc as ldc

    if th.run is not ldc._run_input_threshold:
        errors.append("input_threshold must be logic_dc._run_input_threshold")
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
    # Dual-rail still dispatched (no Path B model on rs0204)
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


def check_logic_dc() -> list[str]:
    errors: list[str] = []
    errors += _no_part_name_ifs(_LOGIC_DC)
    errors += _no_part_name_ifs(_MODEL)
    if not has_product_model("rs1g08") or not has_product_model("rs1g97"):
        errors.append("rs1g08 and rs1g97 must carry product_model schema")
    errors += _and_isolation_ok()
    errors += _97_isolation_ok()
    errors += _buf126_ok()
    errors += _seelim_wrap_ok()
    errors += _registry_ok()
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
        "OK logic-dc: shared logic_dc.py + product_model for rs1g08/rs1g97/rs1g126 "
        "(97 datasheet truth table; seelim locator not runtime; 126 keeps ioz+ten/tdis)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
