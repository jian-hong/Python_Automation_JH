"""RS0204 dual-rail translator TestSpecs.

Downloads/logic_test.py is a Soo dispatcher that cannot import
(test_input_thresholds missing), passes vccb into single-rail IDD, and uses
TP/TIDLE/TDIS/TEN/IDD/VOUT/CAP instead of the lab-report sheets.

This module does not import Soo.* . PSU CH1=VCCA, CH2=VCCB.
Workbook Tsu/Th = datasheet ten/tdis. Cpd here is pin Cio via DMM cap.
"""
from __future__ import annotations

import time
from typing import Any

import yaml

from ate.core.paths import PARTS_DIR
from ate.core.registry import TestSpec, register
from ate.core.run_params import RunParams

_FIXTURE = "LOGIC"
_PART = "rs0204"
_NOTE = "Dual-rail VCCA/VCCB. Not RS29511/Soo."

CASES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    ("vih", "VIH", "VIH", frozenset({"PSU", "DMM", "AWG"})),
    ("vil", "VIL", "VIL", frozenset({"PSU", "DMM", "AWG"})),
    ("voh", "VOH", "VOH", frozenset({"PSU", "DMM", "AWG"})),
    ("vol", "VOL", "VOL", frozenset({"PSU", "DMM", "AWG"})),
    ("icc", "Icc", "Icc", frozenset({"PSU", "DMM", "AWG"})),
    ("il", "Il", "Il", frozenset({"PSU", "DMM", "AWG"})),
    ("tpd", "Tpd", "Tpd", frozenset({"MSO", "PSU", "AWG"})),
    ("tp_rs0204", "Tp", "Tp", frozenset({"MSO", "PSU", "AWG"})),
    ("tsu", "Tsu", "Tsu", frozenset({"MSO", "PSU", "AWG"})),
    ("th", "Th", "Th", frozenset({"MSO", "PSU", "AWG"})),
    ("fmax", "fmax", "fmax", frozenset({"MSO", "PSU", "AWG"})),
    ("tr", "tr", "tr", frozenset({"MSO", "PSU", "AWG"})),
    ("tf", "tf", "tf", frozenset({"MSO", "PSU", "AWG"})),
    ("tsk", "Tsk", "Tsk", frozenset({"MSO", "PSU", "AWG"})),
    ("cpd", "Cpd", "Cpd", frozenset({"DMM"})),
    ("tw", "tw", "tw", frozenset({"MSO", "PSU", "AWG"})),
)

TEST_IDS: tuple[str, ...] = tuple(c[0] for c in CASES)
LAB_SHEETS: tuple[str, ...] = tuple(c[2] for c in CASES)


def _part_cfg() -> dict[str, Any]:
    path = PARTS_DIR / f"{_PART}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def rails_from_params(params: RunParams) -> tuple[float, float, float]:
    """VCCA, VCCB, current_limit_a. VCCA must be <= VCCB."""
    cfg = _part_cfg()
    vcca = float(getattr(params, "vcc", None) or cfg.get("vcca") or cfg.get("vcc") or 1.8)
    raw_b = getattr(params, "vccb", None)
    vccb = float(raw_b) if raw_b not in (None, "") else float(cfg.get("vccb") or 3.3)
    if vcca > vccb:
        raise RuntimeError(f"RS0204: VCCA {vcca} V must be <= VCCB {vccb} V")
    ilim = float(getattr(params, "current_limit_a", None) or cfg.get("current_limit") or 0.05)
    return vcca, vccb, ilim


def _require(instr, *names: str) -> None:
    remap = {"MSO": "scope", "PSU": "psu", "AWG": "gen", "DMM": "dmm"}
    missing = [n for n in names if getattr(instr, remap[n], None) is None]
    if missing:
        raise RuntimeError(f"Missing instruments: {', '.join(missing)}")


def _pause(params: RunParams, title: str) -> bool:
    hook = params.pause_hook
    if hook is None:
        return True
    return bool(hook(title))


def _power_dual(instr, vcca: float, vccb: float, ilim: float) -> None:
    from psu_setup import power_on_protected

    power_on_protected(instr.psu, 1, vcca, ilim)
    power_on_protected(instr.psu, 2, vccb, ilim)
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
        if getattr(instr, "psu", None) is not None:
            power_off(instr.psu)
    except Exception:
        pass


def _oe_enable(instr, vcca: float) -> None:
    from generator_setup import setup_dc

    setup_dc(instr.gen, 2, vcca)


def _avg_v(dmm, n: int = 3) -> float:
    from dmm_setup import dmm_read, dmm_setup_voltage

    dmm_setup_voltage(dmm)
    vals = [float(dmm_read(dmm)) for _ in range(max(1, n))]
    return sum(vals) / len(vals)


def _avg_a(dmm, n: int = 3) -> float:
    from dmm_setup import dmm_read, dmm_setup_current

    dmm_setup_current(dmm)
    vals = [float(dmm_read(dmm)) for _ in range(max(1, n))]
    return sum(vals) / len(vals)


def _run_threshold(instr, params: RunParams, *, rising: bool) -> dict[str, Any]:
    _require(instr, "PSU", "AWG", "DMM")
    from dmm_setup import dmm_read, dmm_setup_voltage
    from generator_setup import setup_dc, stop_output

    vcca, vccb, ilim = rails_from_params(params)
    mid = vccb / 2.0
    found = None
    prev = None
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        dmm_setup_voltage(instr.dmm)
        steps = list(range(0, int(vcca * 100) + 1, 10))
        if not rising:
            steps = list(reversed(steps))
        for i in steps:
            vin = i / 100.0
            setup_dc(instr.gen, 1, vin)
            time.sleep(0.05)
            vout = float(dmm_read(instr.dmm))
            if prev is not None:
                if rising and prev < mid <= vout:
                    found = vin
                if (not rising) and prev >= mid > vout:
                    found = vin
            prev = vout
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    key = "VIH" if rising else "VIL"
    return {
        "summary": f"{key}={found} V @ VCCA={vcca} VCCB={vccb}",
        "data": {"VCCA": vcca, "VCCB": vccb, key: found},
    }


def _run_voh_vol(instr, params: RunParams, *, high: bool) -> dict[str, Any]:
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output

    vcca, vccb, ilim = rails_from_params(params)
    vin = vcca if high else 0.0
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        setup_dc(instr.gen, 1, vin)
        time.sleep(0.2)
        vout = _avg_v(instr.dmm, 5)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    key = "VOH" if high else "VOL"
    if high:
        meas = [{"id": "VOH_DROP_V", "value": max(0.0, vccb - vout), "unit": "V"}]
    else:
        meas = [{"id": "VOL_V", "value": vout, "unit": "V"}]
    return {
        "summary": f"{key}={vout:.4f} V @ Vin={vin} VCCA={vcca} VCCB={vccb}",
        "data": {"VCCA": vcca, "VCCB": vccb, "VIN": vin, key: vout},
        "measurements": meas,
    }


def _run_icc(instr, params: RunParams) -> dict[str, Any]:
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output

    vcca, vccb, ilim = rails_from_params(params)
    _pause(
        params,
        "Icc: DMM in series with VCCA (PSU CH1). AWG CH1=A1 GND, CH2=OE=VCCA. Continue.",
    )
    icca = iccb = 0.0
    try:
        _power_dual(instr, vcca, vccb, ilim)
        setup_dc(instr.gen, 1, 0.0)
        _oe_enable(instr, vcca)
        time.sleep(0.3)
        icca = _avg_a(instr.dmm, 5)
        if not _pause(params, "Icc: move DMM in series with VCCB (PSU CH2). Continue."):
            raise RuntimeError("Icc: operator stopped before ICCB")
        iccb = _avg_a(instr.dmm, 5)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    ua_a = icca * 1e6
    ua_b = iccb * 1e6
    return {
        "summary": f"ICCA={ua_a:.3f} uA ICCB={ua_b:.3f} uA sum={ua_a + ua_b:.3f} uA",
        "data": {"VCCA": vcca, "VCCB": vccb, "ICCA_uA": ua_a, "ICCB_uA": ua_b},
        "measurements": [{"id": "ICC_uA", "value": ua_a + ua_b, "unit": "uA"}],
    }


def _run_il(instr, params: RunParams) -> dict[str, Any]:
    _require(instr, "PSU", "AWG", "DMM")
    from generator_setup import setup_dc, stop_output

    vcca, vccb, ilim = rails_from_params(params)
    _pause(params, "Il: DMM in series with A1 (AWG CH1 -> DMM -> A1). OE=VCCA. Continue.")
    rows: list[dict[str, Any]] = []
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        for vin in (0.0, vcca):
            setup_dc(instr.gen, 1, vin)
            time.sleep(0.3)
            rows.append({"VIN": vin, "IL_uA": _avg_a(instr.dmm, 5) * 1e6})
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    last = rows[-1]["IL_uA"] if rows else float("nan")
    mx = max((abs(float(r["IL_uA"])) for r in rows), default=None)
    return {
        "summary": f"Il n={len(rows)} last={last:.3f} uA",
        "data": {"VCCA": vcca, "VCCB": vccb, "rows": rows},
        "measurements": [{"id": "IL_uA", "value": mx, "unit": "uA"}] if mx is not None else [],
    }


def _run_delay(instr, params: RunParams, *, a_to_b: bool) -> dict[str, Any]:
    _require(instr, "MSO", "PSU", "AWG")
    from generator_setup import setup_square, stop_output
    from scope_setup import measure_delay, scope_setup, set_threshold

    vcca, vccb, ilim = rails_from_params(params)
    drive = vcca if a_to_b else vccb
    freq = float(params.freq_hz or 0) or 400000.0
    if freq < 1000:
        freq = 400000.0
    if a_to_b:
        _pause(
            params,
            "Tpd A->B: AWG CH1=A1 (0..VCCA), scope CH1=A1 CH2=B1, OE=VCCA. Continue.",
        )
    else:
        _pause(
            params,
            "Tp B->A: AWG CH1=B1 (0..VCCB), scope CH1=B1 CH2=A1, OE=VCCA. Continue.",
        )
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        setup_square(instr.gen, 1, freq, drive, drive / 2.0)
        scope_setup(instr.scope, 50e-9, drive / 2.0)
        set_threshold(instr.scope, 1)
        set_threshold(instr.scope, 2)
        t_hl = measure_delay(instr.scope, "FFDelay", 1, 2)
        t_lh = measure_delay(instr.scope, "RRDelay", 1, 2)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    label = "Tpd" if a_to_b else "Tp"
    return {
        "summary": f"{label} tHL={t_hl * 1e9:.2f} ns tLH={t_lh * 1e9:.2f} ns",
        "data": {
            "VCCA": vcca,
            "VCCB": vccb,
            "dir": "A_to_B" if a_to_b else "B_to_A",
            "tPHL_ns": t_hl * 1e9,
            "tPLH_ns": t_lh * 1e9,
        },
    }


def _run_oe_time(instr, params: RunParams, *, enable: bool) -> dict[str, Any]:
    _require(instr, "MSO", "PSU", "AWG")
    from generator_setup import setup_square, stop_output
    from scope_setup import measure_delay, scope_setup, set_threshold

    vcca, vccb, ilim = rails_from_params(params)
    item = "RRDelay" if enable else "FFDelay"
    name = "ten" if enable else "tdis"
    sheet = "Tsu" if enable else "Th"
    _pause(
        params,
        f"{sheet}/{name}: AWG CH1=A1 data, CH2=OE, scope CH1=B1 CH2=OE. Continue.",
    )
    try:
        _power_dual(instr, vcca, vccb, ilim)
        setup_square(instr.gen, 1, 100000, vcca, vcca / 2.0)
        setup_square(instr.gen, 2, 10000, vcca, vcca / 2.0)
        scope_setup(instr.scope, 1e-6, vcca / 2.0)
        set_threshold(instr.scope, 2)
        set_threshold(instr.scope, 1)
        t = measure_delay(instr.scope, item, 2, 1)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    ns = t * 1e9
    return {
        "summary": f"{name}={ns:.2f} ns (workbook {sheet})",
        "data": {"VCCA": vcca, "VCCB": vccb, name.upper() + "_ns": ns},
    }


def _run_edge(instr, params: RunParams, *, rise: bool) -> dict[str, Any]:
    _require(instr, "MSO", "PSU", "AWG")
    from generator_setup import setup_square, stop_output
    from scope_setup import measure_single, scope_setup, set_threshold

    vcca, vccb, ilim = rails_from_params(params)
    item = "RTime" if rise else "FTime"
    key = "tr" if rise else "tf"
    _pause(params, f"{key}: AWG CH1=A1, scope CH1=A1 CH2=B1. Continue.")
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        setup_square(instr.gen, 1, 400000, vcca, vcca / 2.0)
        scope_setup(instr.scope, 20e-9, vccb / 2.0)
        set_threshold(instr.scope, 2)
        t = measure_single(instr.scope, item, 2)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    ns = t * 1e9
    return {
        "summary": f"{key}={ns:.2f} ns (B port)",
        "data": {"VCCA": vcca, "VCCB": vccb, key + "_ns": ns},
    }


def _run_tw(instr, params: RunParams) -> dict[str, Any]:
    _require(instr, "MSO", "PSU", "AWG")
    from generator_setup import setup_pulse, stop_output
    from scope_setup import measure_single, scope_setup, set_threshold

    vcca, vccb, ilim = rails_from_params(params)
    freq = 1e6
    _pause(params, "tw: AWG CH1=A1 pulse, scope CH2=B1. Continue.")
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        setup_pulse(instr.gen, 1, freq, vcca, vcca / 2.0, duty=50)
        scope_setup(instr.scope, 200e-9, vccb / 2.0)
        set_threshold(instr.scope, 2)
        t = measure_single(instr.scope, "PWIDth", 2)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    ns = t * 1e9
    return {
        "summary": f"tw={ns:.2f} ns @ {freq / 1e6:.0f} MHz",
        "data": {"VCCA": vcca, "VCCB": vccb, "tw_ns": ns, "freq_hz": freq},
    }


def _run_tsk(instr, params: RunParams) -> dict[str, Any]:
    _require(instr, "MSO", "PSU", "AWG")
    from generator_setup import setup_square, stop_output
    from scope_setup import measure_delay, scope_setup, set_threshold

    vcca, vccb, ilim = rails_from_params(params)
    _pause(
        params,
        "Tsk: AWG CH1=A1 CH2=A2, scope CH1=B1 CH2=B2. Tie OE to VCCA on the board. Continue.",
    )
    try:
        _power_dual(instr, vcca, vccb, ilim)
        setup_square(instr.gen, 1, 400000, vcca, vcca / 2.0)
        setup_square(instr.gen, 2, 400000, vcca, vcca / 2.0)
        scope_setup(instr.scope, 20e-9, vccb / 2.0)
        set_threshold(instr.scope, 1)
        set_threshold(instr.scope, 2)
        t = measure_delay(instr.scope, "RRDelay", 1, 2)
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    ns = abs(t) * 1e9
    return {
        "summary": f"tsk(O)={ns:.2f} ns (B1 vs B2)",
        "data": {"VCCA": vcca, "VCCB": vccb, "tsk_ns": ns},
    }


def _run_fmax(instr, params: RunParams) -> dict[str, Any]:
    _require(instr, "MSO", "PSU", "AWG")
    from generator_setup import setup_square, stop_output
    from scope_setup import measure_single, scope_setup, set_threshold

    vcca, vccb, ilim = rails_from_params(params)
    # ponytail: AWG frequency ceiling, not datasheet 100 Mbps
    freqs = (1e6, 2e6, 5e6, 10e6, 20e6)
    last_ok = 0.0
    last_vpp = 0.0
    _pause(params, "fmax: AWG CH1=A1, scope CH2=B1. Continue.")
    try:
        _power_dual(instr, vcca, vccb, ilim)
        _oe_enable(instr, vcca)
        floor = 0.5 * vccb
        for f in freqs:
            setup_square(instr.gen, 1, f, vcca, vcca / 2.0)
            scope_setup(instr.scope, max(20e-9, 0.2 / f), vccb / 2.0)
            set_threshold(instr.scope, 2)
            vpp = measure_single(instr.scope, "VPP", 2)
            last_vpp = vpp
            if vpp >= floor:
                last_ok = f
            else:
                break
    finally:
        try:
            stop_output(instr.gen)
        except Exception:
            pass
        _power_down(instr)
    return {
        "summary": f"fmax~{last_ok / 1e6:.1f} Mbps (AWG cap; last Vpp={last_vpp:.3f} V)",
        "data": {"VCCA": vcca, "VCCB": vccb, "fmax_hz": last_ok, "VPP": last_vpp},
    }


def _run_cpd(instr, params: RunParams) -> dict[str, Any]:
    _require(instr, "DMM")
    from dmm_setup import dmm_read, dmm_setup_cap
    from psu_setup import power_off

    _pause(params, "Cpd/Cio: DUT unpowered. DMM CAP on A1 (or B1). Continue.")
    try:
        if getattr(instr, "psu", None) is not None:
            power_off(instr.psu)
    except Exception:
        pass
    dmm_setup_cap(instr.dmm)
    cap = float(dmm_read(instr.dmm))
    pf = cap * 1e12
    return {
        "summary": f"Cio={pf:.2f} pF (pin cap, not dynamic Cpd)",
        "data": {"CAP_pF": pf},
    }


def _run_vih(instr, params: RunParams) -> dict[str, Any]:
    return _run_threshold(instr, params, rising=True)


def _run_vil(instr, params: RunParams) -> dict[str, Any]:
    return _run_threshold(instr, params, rising=False)


def _run_voh(instr, params: RunParams) -> dict[str, Any]:
    return _run_voh_vol(instr, params, high=True)


def _run_vol(instr, params: RunParams) -> dict[str, Any]:
    return _run_voh_vol(instr, params, high=False)


def _run_tpd(instr, params: RunParams) -> dict[str, Any]:
    return _run_delay(instr, params, a_to_b=True)


def _run_tp(instr, params: RunParams) -> dict[str, Any]:
    return _run_delay(instr, params, a_to_b=False)


def _run_tsu(instr, params: RunParams) -> dict[str, Any]:
    return _run_oe_time(instr, params, enable=True)


def _run_th(instr, params: RunParams) -> dict[str, Any]:
    return _run_oe_time(instr, params, enable=False)


def _run_tr(instr, params: RunParams) -> dict[str, Any]:
    return _run_edge(instr, params, rise=True)


def _run_tf(instr, params: RunParams) -> dict[str, Any]:
    return _run_edge(instr, params, rise=False)


_RUN = {
    "vih": _run_vih,
    "vil": _run_vil,
    "voh": _run_voh,
    "vol": _run_vol,
    "icc": _run_icc,
    "il": _run_il,
    "tpd": _run_tpd,
    "tp_rs0204": _run_tp,
    "tsu": _run_tsu,
    "th": _run_th,
    "fmax": _run_fmax,
    "tr": _run_tr,
    "tf": _run_tf,
    "tsk": _run_tsk,
    "cpd": _run_cpd,
    "tw": _run_tw,
}

for _tid, _label, _sheet, _req in CASES:
    register(
        TestSpec(
            id=_tid,
            label=_label,
            required_instruments=_req,
            fixture_mode=_FIXTURE,
            lab_sheet=_sheet,
            run=_RUN[_tid],
            dual_channel=False,
            notes=_NOTE,
        )
    )
