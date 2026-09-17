"""Logic DC product model + SIM for RS1G97 / RS1G126.

Run: python -m ate.core.check_logic_dc

Fails if family load is broken, setup_dc is missing, truth/isolation YAML
is wrong, or shared DC bodies cannot run without VISA.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from ate.core.logic_model import isolation_errors, load_logic_model, rail_combos
from ate.core.registry import all_tests, load_family
from ate.core.run_params import RunParams
from ate.core.specs import enrich_measurement, load_part_specs
from ate.fixture.modes import enabled_tests_for_part
from ate.tests.logic.dc import make_sim_instr


_DC_IDS_97 = (
    "input_thresholds",
    "supply_current_sweep",
    "delta_supply_current",
    "input_leakage_sweep",
    "ioff_leakage",
)
_DC_IDS_126 = _DC_IDS_97 + ("ioz",)
_BANNED_97 = ("vih_vil", "voh_load", "vol_load", "ioz")
_BANNED_126 = ("vih_vil", "voh_load", "vol_load")


def _errors_src(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    out: list[str] = []
    if re.search(r"(?<![\"'\w])input\s*\(", text):
        out.append(f"{path.name}: must not call input()")
    if re.search(r"(?m)^\s*(?:import\s+Ariff\b|from\s+Ariff\b)", text):
        out.append(f"{path.name}: must not import Ariff.*")
    if re.search(r"(?:import\s+Lim\b|from\s+Lim\b|import\s+SeeLim\b|from\s+SeeLim\b)", text):
        out.append(f"{path.name}: must not import Lim.*/SeeLim.*")
    return out


def _run_sim(part: str, test_id: str, vcc: float) -> dict:
    from ate.core.registry import get

    load_family("logic")
    spec = get(test_id)
    if spec is None:
        raise AssertionError(f"{test_id} not registered")
    instr = make_sim_instr()
    params = RunParams(vcc=vcc, part=part, current_limit_a=0.10)
    return spec.run(instr, params)


def _logic_src_must_not_import_runner() -> list[str]:
    logic_dir = Path(__file__).resolve().parents[1] / "tests" / "logic"
    out: list[str] = []
    for name in ("wraps.py", "ariff_dc.py", "dc.py", "rs0204.py"):
        text = (logic_dir / name).read_text(encoding="utf-8")
        if re.search(r"from\s+ate\.core\.runner\s+import", text):
            out.append(f"{name} must import RunParams from ate.core.run_params, not runner")
    wraps = (logic_dir / "wraps.py").read_text(encoding="utf-8")
    if re.search(r"(?m)^_legacy\s*=\s*_load_legacy\(\)", wraps):
        out.append("wraps.py must lazy-import logic_tests (no _legacy = _load_legacy() at import)")
    return out


def check_logic_dc() -> list[str]:
    errors: list[str] = []

    import generator_setup

    if not hasattr(generator_setup, "setup_dc"):
        errors.append("generator_setup.setup_dc missing -- every Logic DC body ImportErrors")
    if not hasattr(generator_setup, "park_generator_idle"):
        errors.append("generator_setup.park_generator_idle missing -- START safe-idle breaks")
    cfg = Path(__file__).resolve().parents[2] / "configurations.py"
    if "class ScopeDevice" not in cfg.read_text(encoding="utf-8"):
        errors.append("configurations.ScopeDevice missing")
    errors += _logic_src_must_not_import_runner()

    class _Gen:
        def __init__(self) -> None:
            self.writes: list[str] = []

        def write(self, cmd: str) -> None:
            self.writes.append(str(cmd))

    gen = _Gen()
    if hasattr(generator_setup, "setup_dc"):
        if generator_setup.setup_dc(gen, 1, 1.65) is not True:
            errors.append("setup_dc must return True on success")
        joined = " ".join(gen.writes).upper()
        if ":APPL" in joined:
            errors.append("setup_dc must not APPL (DG800 APPL turns AC on)")
        if ":OUTP1 ON" not in joined.replace(" ", ""):
            if not any("OUTP1" in w.upper() and "ON" in w.upper() for w in gen.writes):
                errors.append("setup_dc must enable the AWG channel")

    dc_py = Path(__file__).resolve().parents[1] / "tests" / "logic" / "dc.py"
    model_py = Path(__file__).resolve().parents[0] / "logic_model.py"
    errors += _errors_src(dc_py)
    errors += _errors_src(model_py)

    visa_before = "pyvisa" in sys.modules
    legacy_before = "logic_tests" in sys.modules
    try:
        load_family("logic")
    except Exception as exc:
        errors.append(f"load_family(logic) failed: {type(exc).__name__}: {exc}")
        return errors
    if not visa_before and "pyvisa" in sys.modules:
        errors.append(
            "load_family(logic) imported pyvisa -- Logic tests must not import "
            "runner/scope_setup/logic_tests at family load"
        )
    if not legacy_before and "logic_tests" in sys.modules:
        errors.append("load_family(logic) imported logic_tests -- wraps must stay lazy")

    ids = {t.id for t in all_tests()}
    for need in ("ioz", "input_thresholds", "supply_current_sweep", "delta_supply_current"):
        if need not in ids:
            errors.append(f"logic registry missing {need}")

    for pk, need, banned in (
        ("rs1g97", _DC_IDS_97, _BANNED_97),
        ("rs1g126", _DC_IDS_126, _BANNED_126),
    ):
        en = set(enabled_tests_for_part(pk) or [])
        for tid in need:
            if tid not in en:
                errors.append(f"{pk} enabled_tests missing {tid}")
            elif tid not in ids:
                errors.append(f"{pk} enabled {tid} not registered")
        for tid in banned:
            if tid in en:
                errors.append(f"{pk} must not enable {tid}")

    m97 = load_logic_model("rs1g97")
    if m97 is None:
        errors.append("rs1g97 must define logic_dc / logic_inputs")
        return errors
    if m97.inputs != ("A", "B", "C"):
        errors.append(f"rs1g97 logic_inputs want A,B,C got {m97.inputs}")
    if m97.oe is not None:
        errors.append("rs1g97 must not declare OE")
    if not m97.schmitt:
        errors.append("rs1g97 must be schmitt: true")
    if len(rail_combos(m97.icc_pins)) != 8:
        errors.append(f"rs1g97 ICC combos want 8 got {len(rail_combos(m97.icc_pins))}")
    errors.extend(isolation_errors(m97))

    m126 = load_logic_model("rs1g126")
    if m126 is None:
        errors.append("rs1g126 must define logic_dc / logic_inputs")
        return errors
    if "A" not in m126.inputs:
        errors.append(f"rs1g126 logic_inputs want A got {m126.inputs}")
    if m126.oe is None or m126.oe.pin != "OE" or m126.oe.active != "high":
        errors.append(f"rs1g126 oe want OE active high got {m126.oe}")
    if m126.schmitt:
        errors.append("rs1g126 is not Schmitt in the DC table -- schmitt must be false")
    if len(rail_combos(m126.icc_pins)) != 4:
        errors.append(f"rs1g126 ICC combos (A+OE) want 4 got {len(rail_combos(m126.icc_pins))}")
    errors.extend(isolation_errors(m126))

    if load_logic_model("rs1g08") is not None:
        # Fallback path for Ariff 2-input must stay unless that part grows its own block.
        pass

    specs97 = {s["id"]: s for s in load_part_specs("rs1g97")}
    for sid, mode in (
        ("VTPLUS_1p65V", "range"),
        ("ICC_uA", "max-only"),
        ("DELTA_ICC_uA", "max-only"),
    ):
        row = specs97.get(sid) or {}
        if not row:
            errors.append(f"rs1g97 limits missing {sid}")
            continue
        pm = str(row.get("pass_mode") or "")
        if mode == "range" and (row.get("min") is None or row.get("max") is None):
            errors.append(f"{sid} pass_mode range needs min and max")
        if mode == "max-only" and row.get("max") is None:
            errors.append(f"{sid} max-only needs max")
        if pm and pm != mode:
            errors.append(f"{sid} pass_mode {pm!r} want {mode!r}")
    judged = enrich_measurement(
        {"id": "VTPLUS_1p65V", "value": 0.90},
        specs=load_part_specs("rs1g97"),
        test_id="input_thresholds",
    )
    if judged.get("result") != "pass":
        errors.append(f"VTPLUS_1p65V 0.90 should pass, got {judged}")
    judged_fail = enrich_measurement(
        {"id": "VTPLUS_1p65V", "value": 0.2},
        specs=load_part_specs("rs1g97"),
        test_id="input_thresholds",
    )
    if judged_fail.get("result") != "fail":
        errors.append(f"VTPLUS_1p65V 0.2 should fail, got {judged_fail}")

    if "IOZ_uA" not in {s["id"] for s in load_part_specs("rs1g126")}:
        errors.append("rs1g126 limits missing IOZ_uA")

    yaml97 = Path(__file__).resolve().parents[1] / "config" / "parts" / "rs1g97.yaml"
    text97 = yaml97.read_text(encoding="utf-8")
    if "voh_table" in text97 or "vih_vil" in text97.split("enabled_tests:")[-1]:
        if "vih_vil" in (enabled_tests_for_part("rs1g97") or []):
            errors.append("rs1g97 enabled_tests must not list vih_vil")
    if "do not tick ariff vih_vil" not in text97.lower():
        errors.append("rs1g97 yaml must warn not to tick Ariff vih_vil")

    # SIM: actually run TestSpec.run (DEMO does not).
    try:
        icc = _run_sim("rs1g97", "supply_current_sweep", 5.0)
        n = len((icc.get("data") or {}).get("rows") or [])
        if n != 5 * 8:
            errors.append(f"rs1g97 ICC SIM rows want 40 (5 VCC x 8), got {n}")
        meas = {m["id"]: m for m in icc.get("measurements") or []}
        if "ICC_uA" not in meas:
            errors.append(f"rs1g97 ICC SIM missing ICC_uA: {icc.get('measurements')}")
    except Exception as exc:
        errors.append(f"rs1g97 supply_current_sweep SIM: {type(exc).__name__}: {exc}")

    try:
        th = _run_sim("rs1g97", "input_thresholds", 1.65)
        rows = (th.get("data") or {}).get("rows") or []
        pins = {r.get("PIN") for r in rows}
        if pins != {"A", "B", "C"}:
            errors.append(f"rs1g97 threshold SIM pins {pins} want A,B,C")
        a_row = next((r for r in rows if r.get("PIN") == "A" and abs(float(r["VCC"]) - 1.65) < 1e-6), None)
        if a_row is None or a_row.get("VIH") is None:
            errors.append(f"rs1g97 A @ 1.65V must find VIH with B/C held, got {a_row}")
        meas = {m["id"]: m for m in th.get("measurements") or []}
        vt = meas.get("VTPLUS_1p65V") or {}
        if vt.get("value") is None:
            errors.append(f"rs1g97 SIM missing VTPLUS_1p65V: {meas}")
        else:
            stamped = enrich_measurement(vt, specs=load_part_specs("rs1g97"), test_id="input_thresholds")
            if stamped.get("result") != "pass":
                errors.append(f"rs1g97 SIM VTPLUS_1p65V should pass, got {stamped}")
    except Exception as exc:
        errors.append(f"rs1g97 input_thresholds SIM: {type(exc).__name__}: {exc}")

    for tid in ("delta_supply_current", "input_leakage_sweep", "ioff_leakage"):
        try:
            _run_sim("rs1g97", tid, 5.0)
        except Exception as exc:
            errors.append(f"rs1g97 {tid} SIM: {type(exc).__name__}: {exc}")

    try:
        icc126 = _run_sim("rs1g126", "supply_current_sweep", 5.0)
        n = len((icc126.get("data") or {}).get("rows") or [])
        if n != 4 * 4:
            errors.append(f"rs1g126 ICC SIM rows want 16 (4 VCC x 4), got {n}")
    except Exception as exc:
        errors.append(f"rs1g126 supply_current_sweep SIM: {type(exc).__name__}: {exc}")

    try:
        ioz = _run_sim("rs1g126", "ioz", 3.6)
        meas = {m["id"]: m for m in ioz.get("measurements") or []}
        if "IOZ_uA" not in meas:
            errors.append(f"rs1g126 ioz SIM missing IOZ_uA: {ioz.get('measurements')}")
    except Exception as exc:
        errors.append(f"rs1g126 ioz SIM: {type(exc).__name__}: {exc}")

    for tid in ("input_thresholds", "delta_supply_current", "input_leakage_sweep", "ioff_leakage"):
        try:
            _run_sim("rs1g126", tid, 5.0)
        except Exception as exc:
            errors.append(f"rs1g126 {tid} SIM: {type(exc).__name__}: {exc}")

    try:
        _run_sim("rs1g97", "ioz", 3.6)
        errors.append("rs1g97 ioz SIM must fail (no OE)")
    except RuntimeError:
        pass
    except Exception as exc:
        errors.append(f"rs1g97 ioz SIM unexpected {type(exc).__name__}: {exc}")

    return errors


def main() -> int:
    errors = check_logic_dc()
    if errors:
        print("FAIL logic-dc:")
        for line in errors:
            print(f"  - {line}")
        return 1
    print(
        "OK logic-dc: RS1G97/RS1G126 YAML model + isolation + SIM DC "
        "(setup_dc present, no vih_vil on 97, ioz on 126, load_family visa-free)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
