"""Shared Logic DC procedures -- truth-table + pin map from part YAML.

Register only ids that Ariff DC does not already own. Ariff bodies dispatch
here when load_logic_model(part) is not None (RS1G97 / RS1G126).
"""
from __future__ import annotations

import time
from typing import Any, Optional

from ate.core.logic_model import (
    Isolation,
    LogicModel,
    PinStim,
    eval_y,
    load_logic_model,
    load_part_yaml,
    rail_combos,
    vcc_tag,
)
from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams
from ate.core.specs import load_part_specs

_LOGIC_FIXTURE = "LOGIC"
_NOTE = "Shared Logic DC -- part YAML truth/isolation; no vendor imports"


class SimInstruments:
    """No VISA. PinDriver never SCPI in sim mode; dummies exist so _require passes."""

    sim = True

    def __init__(self) -> None:
        self.psu = _DeadBus("PSU")
        self.gen = _DeadBus("AWG")
        self.dmm = _DeadBus("DMM")
        self.scope = None


class _DeadBus:
    def __init__(self, name: str) -> None:
        self.name = name

    def write(self, *_a: Any, **_k: Any) -> None:
        raise RuntimeError(f"SIM {self.name} must not SCPI")

    def query(self, *_a: Any, **_k: Any) -> str:
        raise RuntimeError(f"SIM {self.name} must not SCPI")


def make_sim_instr() -> SimInstruments:
    return SimInstruments()


def _is_sim(instr: Any) -> bool:
    return bool(getattr(instr, "sim", False))


def _sleep(instr: Any, seconds: float) -> None:
    if _is_sim(instr) or seconds <= 0:
        return
    time.sleep(seconds)


def _require(instr: Any, *names: str) -> None:
    remap = {"MSO": "scope", "PSU": "psu", "AWG": "gen", "DMM": "dmm"}
    missing = [n for n in names if getattr(instr, remap[n], None) is None]
    if missing:
        raise RuntimeError(f"Missing instruments: {', '.join(missing)}")


def _current_limit(params: RunParams, cfg: dict[str, Any]) -> float:
    return float(
        getattr(params, "current_limit_a", None)
        or getattr(params, "current_limit", None)
        or cfg.get("current_limit")
        or 0.10
    )


def _vcc_list(cfg: dict[str, Any], model: LogicModel, params: RunParams) -> list[float]:
    raw = cfg.get("vcc_sweep_list") or cfg.get("vcc_sweep")
    if isinstance(raw, list) and raw:
        return [float(v) for v in raw]
    return [float(params.vcc)]


def _settle(cfg: dict[str, Any]) -> float:
    timing = cfg.get("timing") if isinstance(cfg.get("timing"), dict) else {}
    return float(timing.get("settle_s") or 0.3)


class PinDriver:
    """Apply H/L/analog on AWG or PSU pins; DMM Y or current. SIM uses the truth table."""

    def __init__(self, instr: Any, model: LogicModel, params: RunParams, cfg: dict[str, Any]):
        self.instr = instr
        self.model = model
        self.params = params
        self.cfg = cfg
        self.sim = _is_sim(instr)
        self.ilim = _current_limit(params, cfg)
        self.settle = 0.0 if self.sim else _settle(cfg)
        self._volts: dict[str, float] = {}
        self._vcc = 0.0
        self._psu_on: set[int] = set()
        self._dmm_mode = ""
        self._schmitt: dict[str, bool] = {}
        self._specs = load_part_specs(model.part_key)
        self._vt_cache: dict[float, tuple[float, float]] = {}

    def power(self, vcc: float) -> None:
        self._vcc = float(vcc)
        ovp = max(5.6, float(vcc) * 1.1)
        if self.sim:
            return
        from psu_setup import power_on_protected

        power_on_protected(self.instr.psu, 1, float(vcc), self.ilim, ovp=ovp)
        self._psu_on.add(1)
        _sleep(self.instr, self.settle)

    def shutdown(self) -> None:
        if self.sim:
            return
        from generator_setup import stop_output
        from psu_setup import power_off

        try:
            if getattr(self.instr, "gen", None) is not None:
                stop_output(self.instr.gen)
        except Exception:
            pass
        try:
            power_off(self.instr.psu)
        except Exception:
            pass

    def set_pin(self, pin: str, volts: float) -> bool:
        v = float(volts)
        stim = self.model.stimulus.get(pin)
        if stim is None:
            raise RuntimeError(f"no stimulus map for pin {pin}")
        if stim.src == "psu":
            v = min(v, self.model.psu_vmax)
        self._volts[pin] = v
        if self.sim:
            return True
        if stim.src == "awg":
            from generator_setup import setup_dc

            return bool(setup_dc(self.instr.gen, stim.ch, v))
        return self._psu_force(stim, v)

    def apply_bits(self, bits: dict[str, str], *, high_v: float) -> bool:
        ok = True
        for pin, level in bits.items():
            target = 0.0 if level == "L" else float(high_v)
            if not self.set_pin(pin, target):
                ok = False
        _sleep(self.instr, self.settle)
        return ok

    def apply_isolation(self, spec: Isolation, vin: float) -> bool:
        bits = dict(spec.hold)
        ok = True
        for pin, level in bits.items():
            hv = self._vcc
            if not self.set_pin(pin, 0.0 if level == "L" else hv):
                ok = False
        if self.model.oe is not None and self.model.oe.pin not in spec.hold:
            if not self.set_pin(self.model.oe.pin, self._oe_active_v()):
                ok = False
        if not self.set_pin(spec.sweep, float(vin)):
            ok = False
        _sleep(self.instr, 0.0 if self.sim else min(self.settle, 0.05))
        return ok

    def measure_y(self) -> float:
        if self.sim:
            return self._sim_y()
        self._dmm_voltage()
        from dmm_setup import dmm_read

        return float(dmm_read(self.instr.dmm))

    def measure_i_ua(self) -> float:
        if self.sim:
            return self._sim_i_ua()
        from dmm_setup import dmm_read, dmm_setup_current

        if self._dmm_mode != "curr":
            dmm_setup_current(self.instr.dmm)
            self._dmm_mode = "curr"
        n = 3
        readings = [float(dmm_read(self.instr.dmm)) for _ in range(n)]
        return (sum(readings) / len(readings)) * 1e6

    def _oe_active_v(self) -> float:
        if self.model.oe is None:
            return self._vcc
        return self._vcc if self.model.oe.active == "high" else 0.0

    def _psu_force(self, stim: PinStim, volts: float) -> bool:
        try:
            psu = self.instr.psu
            ch = stim.ch
            if ch not in self._psu_on:
                from psu_setup import power_on_protected

                ovp = max(5.6, float(volts) * 1.1, self._vcc * 1.1)
                power_on_protected(psu, ch, volts, self.ilim, ovp=ovp)
                self._psu_on.add(ch)
            else:
                psu.write(f":SOUR{ch}:VOLT {volts}")
                psu.write(f":OUTP CH{ch},ON")
            return True
        except Exception:
            return False

    def _dmm_voltage(self) -> None:
        if self._dmm_mode == "volt":
            return
        from dmm_setup import dmm_setup_voltage

        dmm_setup_voltage(self.instr.dmm)
        self._dmm_mode = "volt"

    def _vt(self, vcc: float) -> tuple[float, float]:
        key = round(float(vcc), 4)
        hit = self._vt_cache.get(key)
        if hit is not None:
            return hit
        plus, minus = None, None
        tag = vcc_tag(vcc)
        for spec in self._specs:
            sid = str(spec.get("id") or "")
            if sid == f"VTPLUS_{tag}V":
                mn, mx = spec.get("min"), spec.get("max")
                if mn is not None and mx is not None:
                    plus = (float(mn) + float(mx)) / 2.0
                elif mx is not None:
                    plus = float(mx)
                elif mn is not None:
                    plus = float(mn)
            if sid == f"VTMINUS_{tag}V":
                mn, mx = spec.get("min"), spec.get("max")
                if mn is not None and mx is not None:
                    minus = (float(mn) + float(mx)) / 2.0
                elif mn is not None:
                    minus = float(mn)
                elif mx is not None:
                    minus = float(mx)
        if plus is None:
            plus = vcc * 0.60
        if minus is None:
            minus = vcc * 0.40
        if minus > plus:
            minus, plus = plus, minus
        self._vt_cache[key] = (plus, minus)
        return plus, minus

    def _sim_y(self) -> float:
        vcc = self._vcc or 5.0
        bits: dict[str, str] = {}
        analog: Optional[tuple[str, float]] = None
        for pin in self.model.drive_pins:
            v = float(self._volts.get(pin, 0.0))
            if abs(v) < 0.03:
                bits[pin] = "L"
            elif abs(v - vcc) < 0.08 or abs(v - self.model.icc_vi) < 0.08:
                bits[pin] = "H"
            elif abs(v - self.model.psu_vmax) < 0.08 and v >= vcc - 0.2:
                bits[pin] = "H"
            else:
                analog = (pin, v)
        if analog is not None:
            pin, v = analog
            if self.model.schmitt:
                high = self._schmitt.get(pin, False)
                vt_p, vt_m = self._vt(vcc)
                if v >= vt_p:
                    high = True
                elif v <= vt_m:
                    high = False
                self._schmitt[pin] = high
                bits[pin] = "H" if high else "L"
            else:
                bits[pin] = "H" if v >= (vcc / 2.0) else "L"
        y = eval_y(self.model, bits)
        if y == "Z":
            return float(self._volts.get("Y_force", vcc / 2.0))
        if y == "H":
            return vcc * 0.98
        return vcc * 0.02

    def _sim_i_ua(self) -> float:
        vcc = self._vcc
        offset = self.model.delta_icc_offset_v
        for pin, v in self._volts.items():
            if pin in self.model.drive_pins and abs(abs(v) - abs(vcc - offset)) < 0.05:
                return 40.0
        if vcc <= 0.05:
            return 0.15
        return 0.20


def run_supply_current_sweep(
    instr: Any, params: RunParams, model: Optional[LogicModel] = None
) -> dict[str, Any]:
    model = model or load_logic_model(getattr(params, "part", "") or "")
    if model is None:
        raise RuntimeError("supply_current_sweep: no logic_dc model")
    _require(instr, "PSU", "AWG", "DMM")
    cfg = load_part_yaml(model.part_key)
    pins = model.icc_pins
    combos = rail_combos(pins)
    vccs = _vcc_list(cfg, model, params)
    drv = PinDriver(instr, model, params, cfg)
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vccs:
            drv.power(float(vcc))
            # datasheet ICC: VI=5.5V or GND. AWG can 5.5; DP832 CH3 caps at psu_vmax.
            for bits in combos:
                highs = {
                    p: (0.0 if bits[p] == "L" else _high_for(model, p, model.icc_vi))
                    for p in bits
                }
                ok = True
                for p, v in highs.items():
                    if not drv.set_pin(p, v):
                        ok = False
                if not ok:
                    continue
                _sleep(instr, drv.settle)
                i_ua = drv.measure_i_ua()
                row = {"VCC": float(vcc), "IDD_uA": i_ua}
                row.update({f"INPUT_{p}": bits[p] for p in bits})
                rows.append(row)
        if not rows:
            raise RuntimeError("supply_current_sweep: no points measured")
    finally:
        drv.shutdown()
    mx = max(abs(float(r["IDD_uA"])) for r in rows)
    last = rows[-1]
    return {
        "summary": f"ICC 2^{len(pins)} n={len(rows)} max={mx:.3f} uA last={last['IDD_uA']:.3f}",
        "data": {"rows": rows, "pins": list(pins)},
        "measurements": [{"id": "ICC_uA", "value": mx, "unit": "uA"}],
    }


def run_delta_supply_current(
    instr: Any, params: RunParams, model: Optional[LogicModel] = None
) -> dict[str, Any]:
    model = model or load_logic_model(getattr(params, "part", "") or "")
    if model is None:
        raise RuntimeError("delta_supply_current: no logic_dc model")
    _require(instr, "PSU", "AWG", "DMM")
    cfg = load_part_yaml(model.part_key)
    pins = model.icc_pins
    vccs = [
        v
        for v in _vcc_list(cfg, model, params)
        if float(v) + 1e-9 >= model.delta_icc_vcc_min
    ]
    if not vccs:
        vccs = [max(float(params.vcc), model.delta_icc_vcc_min)]
    drv = PinDriver(instr, model, params, cfg)
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vccs:
            drv.power(float(vcc))
            others = [p for p in pins]
            for swept in pins:
                rest = [p for p in others if p != swept]
                for rest_bits in rail_combos(rest) or [{}]:
                    bits = dict(rest_bits)
                    ok = True
                    for p, lv in bits.items():
                        if not drv.set_pin(p, 0.0 if lv == "L" else float(vcc)):
                            ok = False
                    offset = float(vcc) - model.delta_icc_offset_v
                    if not drv.set_pin(swept, offset):
                        ok = False
                    if not ok:
                        continue
                    _sleep(instr, drv.settle)
                    i_ua = drv.measure_i_ua()
                    row = {
                        "VCC": float(vcc),
                        "SWEPT": swept,
                        "OFFSET_V": offset,
                        "IDD_uA": i_ua,
                    }
                    row.update({f"INPUT_{p}": bits.get(p, "offset") for p in pins})
                    rows.append(row)
        if not rows:
            raise RuntimeError("delta_supply_current: no points measured")
    finally:
        drv.shutdown()
    mx = max(abs(float(r["IDD_uA"])) for r in rows)
    return {
        "summary": f"DeltaICC n={len(rows)} max={mx:.3f} uA",
        "data": {"rows": rows},
        "measurements": [{"id": "DELTA_ICC_uA", "value": mx, "unit": "uA"}],
    }


def run_input_thresholds(
    instr: Any, params: RunParams, model: Optional[LogicModel] = None
) -> dict[str, Any]:
    model = model or load_logic_model(getattr(params, "part", "") or "")
    if model is None:
        raise RuntimeError("input_thresholds: no logic_dc model")
    if not model.isolation:
        raise RuntimeError("input_thresholds: threshold_isolation missing in YAML")
    _require(instr, "PSU", "AWG", "DMM")
    cfg = load_part_yaml(model.part_key)
    vccs = _vcc_list(cfg, model, params)
    step = max(0.01, float(model.threshold_step_v))
    drv = PinDriver(instr, model, params, cfg)
    rows: list[dict[str, Any]] = []
    meas: list[dict[str, Any]] = []
    try:
        if not drv.sim:
            from dmm_setup import dmm_setup_voltage

            dmm_setup_voltage(instr.dmm)
            drv._dmm_mode = "volt"
        for vcc in vccs:
            drv.power(float(vcc))
            drv._schmitt.clear()
            for spec in model.isolation:
                vih, vil = _sweep_thresholds(drv, spec, float(vcc), step)
                hyst = None
                if vih is not None and vil is not None:
                    hyst = round(float(vih) - float(vil), 4)
                tag = vcc_tag(vcc)
                rows.append(
                    {
                        "VCC": float(vcc),
                        "PIN": spec.sweep,
                        "HOLD": dict(spec.hold),
                        "VIH": vih,
                        "VIL": vil,
                        "HYSTERESIS_V": hyst,
                        "SCHMITT": model.schmitt,
                    }
                )
                if spec is model.isolation[0]:
                    if vih is not None:
                        meas.append(
                            {"id": f"VTPLUS_{tag}V", "value": vih, "unit": "V"}
                        )
                    if vil is not None:
                        meas.append(
                            {"id": f"VTMINUS_{tag}V", "value": vil, "unit": "V"}
                        )
                    if hyst is not None:
                        meas.append(
                            {"id": f"HYST_{tag}V", "value": hyst, "unit": "V"}
                        )
        if not rows:
            raise RuntimeError("input_thresholds: no VCC/pin points")
        missing = [r for r in rows if r["VIH"] is None and r["VIL"] is None]
        if missing:
            raise RuntimeError(
                "input_thresholds: no Y transition "
                f"(pin={missing[0]['PIN']} hold={missing[0]['HOLD']}). "
                "Fix threshold_isolation so Y tracks the swept pin."
            )
    finally:
        drv.shutdown()
    last = rows[-1]
    return {
        "summary": (
            f"VT n={len(rows)} last {last['PIN']} "
            f"VIH={last['VIH']} VIL={last['VIL']} @ {last['VCC']} V"
        ),
        "data": {"rows": rows},
        "measurements": meas,
    }


def run_ioff_leakage(
    instr: Any, params: RunParams, model: Optional[LogicModel] = None
) -> dict[str, Any]:
    model = model or load_logic_model(getattr(params, "part", "") or "")
    if model is None:
        raise RuntimeError("ioff_leakage: no logic_dc model")
    _require(instr, "PSU", "AWG", "DMM")
    cfg = load_part_yaml(model.part_key)
    vccs = list(model.ioff_vcc_list) or [0.0]
    pins = list(model.drive_pins)
    combos = rail_combos(pins)
    drv = PinDriver(instr, model, params, cfg)
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vccs:
            drv.power(float(vcc))
            for bits in combos:
                for y_bit in ("L", "H"):
                    ok = True
                    for p, lv in bits.items():
                        if not drv.set_pin(
                            p, 0.0 if lv == "L" else _high_for(model, p, model.icc_vi)
                        ):
                            ok = False
                    yv = 0.0 if y_bit == "L" else model.icc_vi
                    if not drv.set_pin("Y_force", min(yv, model.psu_vmax) if yv else 0.0):
                        ok = False
                    if not ok:
                        continue
                    _sleep(instr, drv.settle)
                    i_ua = drv.measure_i_ua()
                    row = {
                        "VCC": float(vcc),
                        "Voltage_Y": yv,
                        "IOFF_uA": i_ua,
                    }
                    row.update({f"Voltage_{p}": bits[p] for p in bits})
                    rows.append(row)
        if not rows:
            raise RuntimeError("ioff_leakage: no points measured")
    finally:
        drv.shutdown()
    mx = max(abs(float(r["IOFF_uA"])) for r in rows)
    return {
        "summary": f"IOFF n={len(rows)} max={mx:.3f} uA",
        "data": {"rows": rows},
        "measurements": [{"id": "IOFF_uA", "value": mx, "unit": "uA"}],
    }


def run_input_leakage_sweep(
    instr: Any, params: RunParams, model: Optional[LogicModel] = None
) -> dict[str, Any]:
    """Supply-path current vs input rails. True pin-II needs DMM on the input -- GAP."""
    model = model or load_logic_model(getattr(params, "part", "") or "")
    if model is None:
        raise RuntimeError("input_leakage_sweep: no logic_dc model")
    _require(instr, "PSU", "AWG", "DMM")
    cfg = load_part_yaml(model.part_key)
    pins = model.icc_pins
    combos = rail_combos(pins)
    vccs = _vcc_list(cfg, model, params)
    drv = PinDriver(instr, model, params, cfg)
    rows: list[dict[str, Any]] = []
    try:
        for vcc in vccs:
            drv.power(float(vcc))
            high = model.icc_vi
            for bits in combos:
                ok = True
                for p, lv in bits.items():
                    if not drv.set_pin(p, 0.0 if lv == "L" else _high_for(model, p, high)):
                        ok = False
                if not ok:
                    continue
                _sleep(instr, drv.settle)
                i_ua = drv.measure_i_ua()
                row = {"VCC": float(vcc), "ILEAK_uA": i_ua}
                row.update({f"INPUT_{p}": bits[p] for p in bits})
                rows.append(row)
        if not rows:
            raise RuntimeError("input_leakage_sweep: no points measured")
    finally:
        drv.shutdown()
    mx = max(abs(float(r["ILEAK_uA"])) for r in rows)
    return {
        "summary": f"Ileak n={len(rows)} max={mx:.3f} uA (supply path; pin-II GAP)",
        "data": {"rows": rows, "note": "DMM on VCC path unless fixture routes pin II"},
        "measurements": [{"id": "II_uA", "value": mx, "unit": "uA"}],
    }


def run_ioz(instr: Any, params: RunParams, model: Optional[LogicModel] = None) -> dict[str, Any]:
    model = model or load_logic_model(getattr(params, "part", "") or "")
    if model is None or model.oe is None:
        raise RuntimeError("ioz requires logic_dc.oe on the part YAML")
    _require(instr, "PSU", "AWG", "DMM")
    cfg = load_part_yaml(model.part_key)
    vcc = float(model.ioz_vcc if model.ioz_vcc is not None else 3.6)
    drv = PinDriver(instr, model, params, cfg)
    rows: list[dict[str, Any]] = []
    try:
        drv.power(vcc)
        inactive = 0.0 if model.oe_inactive_level() == "L" else _high_for(model, model.oe.pin, vcc)
        if not drv.set_pin(model.oe.pin, inactive):
            raise RuntimeError("ioz: failed to hold OE inactive")
        # data inputs at known rails so they do not float
        for p in model.inputs:
            drv.set_pin(p, 0.0)
        for vo in model.ioz_vo_list or (0.0, 5.5):
            force = min(float(vo), model.psu_vmax) if float(vo) else 0.0
            if not drv.set_pin("Y_force", force):
                continue
            _sleep(instr, drv.settle)
            i_ua = drv.measure_i_ua()
            rows.append({"VCC": vcc, "OE": model.oe_inactive_level(), "VO": float(vo), "IOZ_uA": i_ua})
        if not rows:
            raise RuntimeError("ioz: no points measured")
    finally:
        drv.shutdown()
    mx = max(abs(float(r["IOZ_uA"])) for r in rows)
    return {
        "summary": f"IOZ n={len(rows)} max={mx:.3f} uA @ VCC={vcc}",
        "data": {"rows": rows},
        "measurements": [{"id": "IOZ_uA", "value": mx, "unit": "uA"}],
    }


def _high_for(model: LogicModel, pin: str, high_v: float) -> float:
    stim = model.stimulus.get(pin)
    if stim is not None and stim.src == "psu":
        return min(float(high_v), model.psu_vmax)
    return float(high_v)


def _high_for_force(model: LogicModel, high_v: float) -> float:
    return min(float(high_v), model.psu_vmax)


def _sweep_thresholds(
    drv: PinDriver, spec: Isolation, vcc: float, step: float
) -> tuple[Optional[float], Optional[float]]:
    vih: Optional[float] = None
    vil: Optional[float] = None
    prev: Optional[float] = None
    n = int(round(vcc / step))
    for i in range(0, n + 1):
        vin = min(vcc, i * step)
        drv.apply_isolation(spec, vin)
        vout = drv.measure_y()
        if prev is not None and prev < vcc / 2 <= vout:
            vih = vin
        if prev is not None and prev >= vcc / 2 > vout:
            vih = vin  # inverted isolation: Y falls on rising vin
        prev = vout
    prev = None
    for i in range(n, -1, -1):
        vin = min(vcc, i * step)
        drv.apply_isolation(spec, vin)
        vout = drv.measure_y()
        if prev is not None and prev >= vcc / 2 > vout:
            vil = vin
        if prev is not None and prev < vcc / 2 <= vout:
            vil = vin
        prev = vout
    return vih, vil


def _run_ioz(instr: Any, params: RunParams) -> dict[str, Any]:
    return run_ioz(instr, params)


register(
    TestSpec(
        id="ioz",
        label="IOZ (OE disabled)",
        required_instruments=frozenset({"PSU", "AWG", "DMM"}),
        fixture_mode=_LOGIC_FIXTURE,
        lab_sheet="IOZ",
        run=_run_ioz,
        dual_channel=False,
        notes=_NOTE,
    )
)
