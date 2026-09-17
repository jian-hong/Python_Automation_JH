"""Ariff / RS1G Logic DC TestSpecs (A09 + A12).

Native bodies modeled on Ariff Repo LabAutomation_v1 - Copy/logic_tests.py
(2026-09-03 16:41). Do not import Ariff.* / configurations.py / limits.py.
Limits and sweep tables live in part YAML.

Ids voh_load / vol_load avoid clobbering RS0204's voh / vol in the same
Logic registry. supply_current_sweep avoids clobbering Soo supply_current.
"""
from __future__ import annotations

import time
from typing import Any

import yaml

from ate.core.paths import PARTS_DIR
from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams

_LOGIC_FIXTURE = "LOGIC"
_NOTE = "Ariff Logic DC (A12) — params from part YAML; no import Ariff.*"

# Defaults when part yaml omits tables (RS1G08-class)
_DEFAULT_VOH_ROWS = [
    {"vcc": 2.0, "vref": 0.080, "spec_min": 1.6, "ioh_a": 0.008},
    {"vcc": 3.3, "vref": 0.240, "spec_min": 2.5, "ioh_a": 0.024},
    {"vcc": 4.5, "vref": 0.320, "spec_min": 3.8, "ioh_a": 0.032},
    {"vcc": 5.0, "vref": 0.320, "spec_min": 4.2, "ioh_a": 0.032},
    {"vcc": 5.5, "vref": 0.320, "spec_min": 4.8, "ioh_a": 0.032},
]
_DEFAULT_VOL_ROWS = [
    {"vcc": 2.0, "vref": 4.92, "spec_max": 0.45, "iol_a": 0.008},
    {"vcc": 3.3, "vref": 4.76, "spec_max": 0.55, "iol_a": 0.024},
    {"vcc": 4.5, "vref": 4.68, "spec_max": 0.55, "iol_a": 0.032},
    {"vcc": 5.0, "vref": 4.68, "spec_max": 0.50, "iol_a": 0.032},
    {"vcc": 5.5, "vref": 4.68, "spec_max": 0.45, "iol_a": 0.032},
]


def _part_cfg(params: RunParams) -> dict[str, Any]:
    key = str(getattr(params, "part", None) or "rs1g08").strip().lower()
    path = PARTS_DIR / f"{key}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _current_limit(params: RunParams) -> float:
    cfg = _part_cfg(params)
    return float(
        getattr(params, "current_limit_a", None)
        or getattr(params, "current_limit", None)
        or cfg.get("current_limit")
        or 0.05
    )


def _require(instr, *names: str) -> None:
    remap = {"MSO": "scope", "PSU": "psu", "AWG": "gen", "DMM": "dmm"}
    missing = [n for n in names if getattr(instr, remap[n], None) is None]
    if missing:
        raise RuntimeError(f"Missing instruments: {', '.join(missing)}")


def _power_cycle(instr, vcc: float, current_limit: float, *, ovp: float | None = None) -> None:
    from psu_setup import power_on_protected

    kwargs = {}
    if ovp is not None:
        kwargs["ovp"] = ovp
    power_on_protected(instr.psu, 1, vcc, current_limit, **kwargs)
    time.sleep(0.3)


def _power_down(instr) -> None:
    from generator_setup import stop_output
    from psu_setup import power_off

    try:
        if getattr(instr, "gen", None) is not None:
            stop_output(instr.gen)
    except Exception:
        pass
    try:
        power_off(instr.psu)
    except Exception:
        pass


def _avg_current_ua(dmm, n: int = 5) -> float:
    from dmm_setup import dmm_read, dmm_setup_current

    dmm_setup_current(dmm)
    readings = [float(dmm_read(dmm)) for _ in range(n)]
    return (sum(readings) / len(readings)) * 1e6


def _avg_voltage(dmm, n: int = 3) -> float:
    from dmm_setup import dmm_read, dmm_setup_voltage

    dmm_setup_voltage(dmm)
    readings = [float(dmm_read(dmm)) for _ in range(n)]
    return sum(readings) / len(readings)


def _vcc_list(cfg: dict[str, Any], key: str, default: list[float]) -> list[float]:
    raw = cfg.get(key)
    if isinstance(raw, list) and raw:
        return [float(v) for v in raw]
    return list(default)


def _run_delta_supply_current(instr, params: RunParams) -> dict[str, Any]:
    from ate.core.logic_model import load_logic_model
    from ate.tests.logic.dc import run_delta_supply_current

    model = load_logic_model(getattr(params, "part", "") or "")
    if model is not None:
        return run_delta_supply_current(instr, params, model=model)
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output

    vcc = float(params.vcc)
    ilim = _current_limit(params)
    # Ariff Repo uses near-threshold (vcc-0.6) patterns; keep that
    combos = [(vcc - 0.6, vcc), (vcc - 0.6, 0.0), (vcc, vcc - 0.6), (0.0, vcc - 0.6)]
    rows: list[dict[str, Any]] = []
    try:
        _power_cycle(instr, vcc, ilim, ovp=5.6)
        setup_dc(instr.gen, 1, 0.0)
        setup_dc(instr.gen, 2, 0.0)
        for a_v, b_v in combos:
            if not setup_dc(instr.gen, 1, a_v) or not setup_dc(instr.gen, 2, b_v):
                continue
            time.sleep(0.5)
            idd = _avg_current_ua(instr.dmm)
            rows.append({"VCC": vcc, "INPUT_A_V": a_v, "INPUT_B_V": b_v, "IDD_uA": idd})
        if not rows:
            raise RuntimeError("delta_supply_current: no successful AWG DC setups")
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    last = rows[-1]
    return {
        "summary": f"DeltaIDD n={len(rows)} last={last['IDD_uA']:.3f} uA @ {vcc} V",
        "data": {"rows": rows, "VCC": vcc},
    }


def _run_off_current(instr, params: RunParams) -> dict[str, Any]:
    """VCC=0; drive A/B via AWG and Y via PSU CH2 — 8 Ariff combos."""
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output
    from psu_setup import power_on_protected

    ilim = _current_limit(params)
    combos = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 5.5),
        (0.0, 5.5, 0.0),
        (0.0, 5.5, 5.5),
        (5.5, 0.0, 0.0),
        (5.5, 0.0, 5.5),
        (5.5, 5.5, 0.0),
        (5.5, 5.5, 5.5),
    ]
    rows: list[dict[str, Any]] = []
    try:
        power_on_protected(instr.psu, 1, 0.0, ilim, ovp=5.6)
        time.sleep(0.5)
        for a_v, b_v, y_v in combos:
            if not setup_dc(instr.gen, 1, a_v) or not setup_dc(instr.gen, 2, b_v):
                continue
            power_on_protected(instr.psu, 2, y_v, ilim, ovp=5.6)
            time.sleep(0.5)
            idd = _avg_current_ua(instr.dmm)
            rows.append(
                {
                    "VCC": 0.0,
                    "INPUT_A_V": a_v,
                    "INPUT_B_V": b_v,
                    "OUTPUT_Y_V": y_v,
                    "IDD_uA": idd,
                }
            )
        if not rows:
            raise RuntimeError("off_current: no successful setups")
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    last = rows[-1]
    return {
        "summary": f"OffCurrent n={len(rows)} last={last['IDD_uA']:.3f} uA",
        "data": {"rows": rows},
    }


def _run_input_thresholds(instr, params: RunParams) -> dict[str, Any]:
    """AWG 0.05 V steps; return VIH/VIL + hysteresis."""
    from ate.core.logic_model import load_logic_model
    from ate.tests.logic.dc import run_input_thresholds

    model = load_logic_model(getattr(params, "part", "") or "")
    if model is not None:
        return run_input_thresholds(instr, params, model=model)
    _require(instr, "PSU", "AWG", "DMM")
    from dmm_setup import dmm_read, dmm_setup_voltage
    from generator_setup import setup_dc, stop_output

    vcc = float(params.vcc)
    ilim = _current_limit(params)
    try:
        _power_cycle(instr, vcc, ilim)
        dmm_setup_voltage(instr.dmm)
        vih = None
        vil = None
        prev = None
        for i in range(0, int(vcc * 100) + 1, 5):
            vin = i / 100.0
            setup_dc(instr.gen, 1, vin)
            time.sleep(0.05)
            vout = float(dmm_read(instr.dmm))
            if prev is not None and prev < vcc / 2 <= vout:
                vih = vin
            prev = vout
        prev = None
        for i in range(int(vcc * 100), -1, -5):
            vin = i / 100.0
            setup_dc(instr.gen, 1, vin)
            time.sleep(0.05)
            vout = float(dmm_read(instr.dmm))
            if prev is not None and prev >= vcc / 2 > vout:
                vil = vin
            prev = vout
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    hyst = None
    if vih is not None and vil is not None:
        hyst = round(float(vih) - float(vil), 4)
    data = {"VCC": vcc, "VIH": vih, "VIL": vil, "HYSTERESIS_V": hyst}
    return {
        "summary": f"VIH={vih} VIL={vil} Hyst={hyst} @ {vcc} V",
        "data": data,
    }


def _run_ioff_leakage(instr, params: RunParams) -> dict[str, Any]:
    """IOFF at VCC list with 8 pin-force combos (A/B AWG, Y PSU CH2)."""
    from ate.core.logic_model import load_logic_model
    from ate.tests.logic.dc import run_ioff_leakage

    model = load_logic_model(getattr(params, "part", "") or "")
    if model is not None:
        return run_ioff_leakage(instr, params, model=model)
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output
    from psu_setup import power_on_protected

    cfg = _part_cfg(params)
    ilim = _current_limit(params)
    vcc_values = _vcc_list(cfg, "ioff_vcc_list", [0.0, 5.5])
    combos = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 5.5),
        (0.0, 5.5, 0.0),
        (0.0, 5.5, 5.5),
        (5.5, 0.0, 0.0),
        (5.5, 0.0, 5.5),
        (5.5, 5.5, 0.0),
        (5.5, 5.5, 5.5),
    ]
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vcc_values:
            power_on_protected(instr.psu, 1, float(vcc), ilim, ovp=5.6)
            time.sleep(0.5)
            any_ok = False
            for a_v, b_v, y_v in combos:
                ok_a = setup_dc(instr.gen, 1, a_v)
                ok_b = setup_dc(instr.gen, 2, b_v)
                power_on_protected(instr.psu, 2, y_v, ilim, ovp=5.6)
                time.sleep(0.5)
                if not (ok_a and ok_b):
                    continue
                any_ok = True
                ioff = _avg_current_ua(instr.dmm)
                rows.append(
                    {
                        "VCC": float(vcc),
                        "Voltage_A": a_v,
                        "Voltage_B": b_v,
                        "Voltage_Y": y_v,
                        "IOFF_uA": ioff,
                    }
                )
                try:
                    stop_output(instr.gen)
                except Exception:
                    pass
                power_on_protected(instr.psu, 2, 0.0, ilim)
            if not any_ok:
                raise RuntimeError(f"ioff_leakage: setup failed at VCC={vcc}")
    finally:
        _power_down(instr)
    last = rows[-1]
    return {
        "summary": f"IoffLeakage n={len(rows)} last={last['IOFF_uA']:.3f} uA",
        "data": {"rows": rows},
    }


def _run_input_leakage_sweep(instr, params: RunParams) -> dict[str, Any]:
    """IDD-style leakage vs VCC list x 4 input combos (YAML-capped by default)."""
    from ate.core.logic_model import load_logic_model
    from ate.tests.logic.dc import run_input_leakage_sweep

    model = load_logic_model(getattr(params, "part", "") or "")
    if model is not None:
        return run_input_leakage_sweep(instr, params, model=model)
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output

    cfg = _part_cfg(params)
    ilim = _current_limit(params)
    # Default short list; full 0..5.6/0.1 via part yaml vcc_sweep_list
    vcc_values = _vcc_list(cfg, "vcc_sweep_list", [0.0, 1.65, 3.3, 5.0, 5.5])
    combos = [(0.0, 0.0), (0.0, 5.5), (5.5, 0.0), (5.5, 5.5)]
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vcc_values:
            _power_cycle(instr, float(vcc), ilim, ovp=5.6)
            time.sleep(0.3)
            for a_v, b_v in combos:
                if not setup_dc(instr.gen, 1, a_v) or not setup_dc(instr.gen, 2, b_v):
                    continue
                time.sleep(0.3)
                i_ua = _avg_current_ua(instr.dmm)
                rows.append(
                    {
                        "VCC": float(vcc),
                        "INPUT_A_V": a_v,
                        "INPUT_B_V": b_v,
                        "ILEAK_uA": i_ua,
                    }
                )
        if not rows:
            raise RuntimeError("input_leakage_sweep: no points measured")
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    last = rows[-1]
    return {
        "summary": f"IleakSweep n={len(rows)} last={last['ILEAK_uA']:.3f} uA",
        "data": {"rows": rows},
    }


def _run_supply_current_sweep(instr, params: RunParams) -> dict[str, Any]:
    """Ariff IDD vs VCC x 4 input combos. Distinct from Soo supply_current."""
    from ate.core.logic_model import load_logic_model
    from ate.tests.logic.dc import run_supply_current_sweep

    model = load_logic_model(getattr(params, "part", "") or "")
    if model is not None:
        return run_supply_current_sweep(instr, params, model=model)
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output

    cfg = _part_cfg(params)
    ilim = _current_limit(params)
    vcc_values = _vcc_list(cfg, "vcc_sweep_list", [1.65, 3.3, 5.0, 5.5])
    combos = [(0.0, 0.0), (0.0, 5.5), (5.5, 0.0), (5.5, 5.5)]
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vcc_values:
            _power_cycle(instr, float(vcc), ilim, ovp=5.6)
            time.sleep(0.5)
            any_ok = False
            for a_v, b_v in combos:
                if not setup_dc(instr.gen, 1, a_v) or not setup_dc(instr.gen, 2, b_v):
                    continue
                any_ok = True
                time.sleep(0.5)
                idd = _avg_current_ua(instr.dmm)
                rows.append(
                    {
                        "VCC": float(vcc),
                        "INPUT_A_V": a_v,
                        "INPUT_B_V": b_v,
                        "IDD_uA": idd,
                    }
                )
            if not any_ok:
                raise RuntimeError(f"supply_current_sweep: setup failed at VCC={vcc}")
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    last = rows[-1]
    mx = max(abs(float(r["IDD_uA"])) for r in rows)
    return {
        "summary": f"SupplySweep n={len(rows)} last={last['IDD_uA']:.3f} uA",
        "data": {"rows": rows},
        "measurements": [{"id": "ICC_uA", "value": mx, "unit": "uA"}],
    }


def _run_vih_vil(instr, params: RunParams) -> dict[str, Any]:
    """PSU-rail VIH/VIL at each VCC in yaml list (A held high via AWG CH2).

    Ariff Repo uses 3 PSU channels; platform path uses PSU CH1=VCC + AWG A/B
    so a single DP832 + DG811 still works. Limits optional in part yaml.
    """
    _require(instr, "PSU", "AWG", "DMM")
    from dmm_setup import dmm_read, dmm_setup_voltage
    from generator_setup import setup_dc, stop_output

    cfg = _part_cfg(params)
    ilim = _current_limit(params)
    vcc_list = _vcc_list(cfg, "vih_vil_vcc_list", [2.0, 3.3, 5.0])
    # Optional {vcc: {vih_max, vil_min}} — miss = no pass/fail
    limits = cfg.get("vih_vil_limits") if isinstance(cfg.get("vih_vil_limits"), dict) else {}
    rows: list[dict[str, Any]] = []
    try:
        dmm_setup_voltage(instr.dmm)
        for vcc in vcc_list:
            vcc = float(vcc)
            _power_cycle(instr, vcc, ilim, ovp=max(5.6, vcc * 1.1))
            # Hold A high (AND other input); sweep B
            setup_dc(instr.gen, 2, vcc)
            vih = None
            vil = None
            prev = None
            for i in range(0, int(vcc * 100) + 1, 5):
                vin = i / 100.0
                setup_dc(instr.gen, 1, vin)
                time.sleep(0.05)
                vout = float(dmm_read(instr.dmm))
                if prev is not None and prev < vcc / 2 <= vout:
                    vih = vin
                prev = vout
            prev = None
            for i in range(int(vcc * 100), -1, -5):
                vin = i / 100.0
                setup_dc(instr.gen, 1, vin)
                time.sleep(0.05)
                vout = float(dmm_read(instr.dmm))
                if prev is not None and prev >= vcc / 2 > vout:
                    vil = vin
                prev = vout
            lim = limits.get(str(vcc)) or limits.get(vcc) or {}
            vih_max = lim.get("vih_max") if isinstance(lim, dict) else None
            vil_min = lim.get("vil_min") if isinstance(lim, dict) else None
            vih_pass = None
            vil_pass = None
            if vih is not None and vih_max is not None:
                vih_pass = float(vih) <= float(vih_max)
            if vil is not None and vil_min is not None:
                vil_pass = float(vil) >= float(vil_min)
            rows.append(
                {
                    "VCC": vcc,
                    "VIH": vih,
                    "VIL": vil,
                    "HYSTERESIS_V": (
                        round(float(vih) - float(vil), 4)
                        if vih is not None and vil is not None
                        else None
                    ),
                    "VIH_pass": vih_pass,
                    "VIL_pass": vil_pass,
                }
            )
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    if not rows:
        raise RuntimeError("vih_vil: no VCC points measured")
    return {
        "summary": f"VIH/VIL n={len(rows)} last VCC={rows[-1]['VCC']}",
        "data": {"rows": rows},
    }


def _run_voh_load(instr, params: RunParams) -> dict[str, Any]:
    """Functional VOH vs YAML table (PSU CH1=VCC, CH2=Vref, CH3=V+)."""
    _require(instr, "PSU", "DMM")
    from psu_setup import power_off, power_on_protected

    cfg = _part_cfg(params)
    rows_cfg = cfg.get("voh_table") if isinstance(cfg.get("voh_table"), list) else None
    if not rows_cfg:
        raise RuntimeError(
            f"{getattr(params, 'part', '')}: voh_load needs part yaml voh_table "
            "(will not inherit RS1G08 default load numbers)"
        )
    vplus = float(cfg.get("vplus_v") or 5.0)
    ilim = _current_limit(params)
    settle = float(cfg.get("voh_vol_settle_s") or 1.0)
    rows: list[dict[str, Any]] = []
    try:
        power_on_protected(instr.psu, 3, vplus, ilim)
        for entry in rows_cfg:
            if not isinstance(entry, dict):
                continue
            vcc = float(entry["vcc"])
            vref = float(entry["vref"])
            spec = float(entry["spec_min"])
            ioh = float(entry.get("ioh_a") or 0.032)
            power_on_protected(instr.psu, 1, vcc, ilim)
            time.sleep(0.2)
            power_on_protected(instr.psu, 2, vref, ioh, ocp=0.05)
            time.sleep(settle)
            measured = _avg_voltage(instr.dmm, n=3)
            ok = measured >= spec
            rows.append(
                {
                    "VCC": vcc,
                    "Vref": vref,
                    "Vplus": vplus,
                    "Measured": measured,
                    "Spec_min": spec,
                    "Result": "PASS" if ok else "FAIL",
                }
            )
            power_off(instr.psu)
            time.sleep(0.5)
            power_on_protected(instr.psu, 3, vplus, ilim)
    finally:
        _power_down(instr)
    if not rows:
        raise RuntimeError("voh_load: empty table")
    n_pass = sum(1 for r in rows if r["Result"] == "PASS")
    meas = [
        {
            "id": f"VOH_{str(r['VCC']).replace('.', 'p')}V",
            "value": r["Measured"],
            "unit": "V",
        }
        for r in rows
        if r.get("Measured") is not None
    ]
    return {
        "summary": f"VOH {n_pass}/{len(rows)} PASS",
        "data": {"rows": rows},
        "measurements": meas,
    }


def _run_vol_load(instr, params: RunParams) -> dict[str, Any]:
    """Functional VOL vs YAML table (same wiring as voh_load)."""
    _require(instr, "PSU", "DMM")
    from psu_setup import power_off, power_on_protected

    cfg = _part_cfg(params)
    rows_cfg = cfg.get("vol_table") if isinstance(cfg.get("vol_table"), list) else None
    if not rows_cfg:
        raise RuntimeError(
            f"{getattr(params, 'part', '')}: vol_load needs part yaml vol_table "
            "(will not inherit RS1G08 default load numbers)"
        )
    vplus = float(cfg.get("vplus_v") or 5.0)
    ilim = _current_limit(params)
    settle = float(cfg.get("voh_vol_settle_s") or 1.0)
    rows: list[dict[str, Any]] = []
    try:
        for entry in rows_cfg:
            if not isinstance(entry, dict):
                continue
            vcc = float(entry["vcc"])
            vref = float(entry["vref"])
            spec = float(entry["spec_max"])
            iol = float(entry.get("iol_a") or 0.032)
            power_on_protected(instr.psu, 1, vcc, ilim)
            time.sleep(0.2)
            power_on_protected(instr.psu, 2, vref, iol, ocp=0.05)
            time.sleep(settle)
            power_on_protected(instr.psu, 3, vplus, ilim)
            time.sleep(0.5)
            measured = _avg_voltage(instr.dmm, n=3)
            ok = measured <= spec
            rows.append(
                {
                    "VCC": vcc,
                    "Vref": vref,
                    "Vplus": vplus,
                    "Measured": measured,
                    "Spec_max": spec,
                    "Result": "PASS" if ok else "FAIL",
                }
            )
            power_off(instr.psu)
            time.sleep(0.5)
    finally:
        _power_down(instr)
    if not rows:
        raise RuntimeError("vol_load: empty table")
    n_pass = sum(1 for r in rows if r["Result"] == "PASS")
    meas = [
        {
            "id": f"VOL_{str(r['VCC']).replace('.', 'p')}V",
            "value": r["Measured"],
            "unit": "V",
        }
        for r in rows
        if r.get("Measured") is not None
    ]
    return {
        "summary": f"VOL {n_pass}/{len(rows)} PASS",
        "data": {"rows": rows},
        "measurements": meas,
    }


def _register(
    test_id: str,
    label: str,
    lab_sheet: str,
    required: frozenset[str],
    run,
) -> None:
    register(
        TestSpec(
            id=test_id,
            label=label,
            required_instruments=required,
            fixture_mode=_LOGIC_FIXTURE,
            lab_sheet=lab_sheet,
            run=run,
            dual_channel=False,
            notes=_NOTE,
        )
    )


_register(
    "delta_supply_current",
    "Delta Supply Current",
    "DeltaIDD",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_delta_supply_current,
)
_register(
    "off_current",
    "Off-State Current",
    "OffCurrent",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_off_current,
)
_register(
    "input_thresholds",
    "Input Thresholds (VIH/VIL AWG)",
    "InputThresholds",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_input_thresholds,
)
_register(
    "ioff_leakage",
    "I/O Off Leakage",
    "IoffLeakage",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_ioff_leakage,
)
_register(
    "input_leakage_sweep",
    "Input Leakage Sweep",
    "InputLeakageSweep",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_input_leakage_sweep,
)
_register(
    "supply_current_sweep",
    "Supply Current Sweep (Ariff)",
    "Supply_Current",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_supply_current_sweep,
)
_register(
    "vih_vil",
    "VIH/VIL (multi-VCC)",
    "VIH_VIL",
    frozenset({"PSU", "AWG", "DMM"}),
    _run_vih_vil,
)
_register(
    "voh_load",
    "VOH (loaded)",
    "VOH",
    frozenset({"PSU", "DMM"}),
    _run_voh_load,
)
_register(
    "vol_load",
    "VOL (loaded)",
    "VOL",
    frozenset({"PSU", "DMM"}),
    _run_vol_load,
)
