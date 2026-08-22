"""MSO5072 helpers — live-session capture only (no second Instruments())."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from scope_setup import capture_scope_png, measure_single, scope_setup, set_threshold

STAT_KEYS = ("CURRent", "AVERages", "MAXimum", "MINimum", "DEViation", "COUNt")


def is_visa_poison(exc: BaseException | str) -> bool:
    """MSO leftover :DISP:DATA? / USB stack death (not a DUT measurement fail)."""
    msg = str(exc)
    return (
        "VI_ERROR" in msg
        or "-1073807360" in msg
        or "system error" in msg.lower()
    )


def capture_jpeg(scope, filepath, timeout_ms: int = 10000, quality: int = 90) -> str:
    from scope_setup import recover_scope_session

    path = Path(filepath)
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        path = path.with_suffix(".jpg")
    try:
        return capture_scope_png(scope, path, timeout_ms=timeout_ms, jpeg_quality=quality)
    except Exception as exc:
        if not is_visa_poison(exc):
            raise
        recover_scope_session(scope, run=True)
        return capture_scope_png(scope, path, timeout_ms=timeout_ms, jpeg_quality=quality)


def apply_scope_preset(scope, preset: dict) -> None:
    """Apply Eugene vertical/horizontal sizing from rs622.yaml scope_presets."""
    if not preset:
        return
    tb = preset.get("timebase")
    trig = preset.get("trig_level", 0)
    if tb is not None:
        scope_setup(scope, tb, trig)
    if "ch1_scale" in preset:
        scope.write(f"CHAN1:SCALe {preset['ch1_scale']}")
    if "ch1_offset" in preset:
        scope.write(f"CHAN1:OFFS {preset['ch1_offset']}")
    if "ch2_scale" in preset:
        scope.write(f"CHAN2:SCALe {preset['ch2_scale']}")
    if "ch2_offset" in preset:
        scope.write(f"CHAN2:OFFS {preset['ch2_offset']}")
    if "time_offset" in preset:
        scope.write(f"TIMebase:OFFSet {preset['time_offset']}")


def _force_chan(scope, ch: int, scale: float | None, offs: float | None) -> None:
    """Write vertical and retry if readback still shows leftover GBW 100 mV etc."""
    try:
        scope.write(f":CHAN{ch}:DISP ON")
    except Exception:
        pass
    last_s = last_o = None
    queried = False
    for _ in range(4):
        if scale is not None:
            scope.write(f":CHAN{ch}:SCALe {scale}")
        if offs is not None:
            scope.write(f":CHAN{ch}:OFFS {offs}")
        time.sleep(0.08)
        try:
            if scale is not None:
                last_s = float(scope.query(f":CHAN{ch}:SCALe?").strip())
                queried = True
                if abs(last_s - scale) > max(0.02 * abs(scale), 0.005):
                    continue
            if offs is not None:
                last_o = float(scope.query(f":CHAN{ch}:OFFS?").strip())
                queried = True
                if abs(last_o - offs) > max(0.08 * abs(offs), 0.015):
                    continue
            return
        except Exception as exc:
            if is_visa_poison(exc):
                raise
            continue
    if not queried:
        return
    raise RuntimeError(
        f"CHAN{ch} scale/offset did not take "
        f"(want {scale}/{offs}, got {last_s}/{last_o})"
    )


def apply_scope_manual(scope, preset: dict) -> None:
    """Apply locked lab-photo scales without :AUToscale."""
    if not preset:
        return
    try:
        scope.write(":CHAN1:COUP DC")
        scope.write(":CHAN2:COUP DC")
        scope.write(":CHAN3:DISP OFF")
        scope.write(":CHAN4:DISP OFF")
    except Exception:
        pass
    tb = preset.get("timebase")
    if tb is not None:
        scope.write(f"TIMebase:MAIN:SCAle {tb}")
    if "time_offset" in preset:
        scope.write(f"TIMebase:OFFSet {preset['time_offset']}")
    slope = str(preset.get("trig_slope", "POS")).upper()
    scope.write(f":TRIGger:EDGE:SLOPe {'POSitive' if slope.startswith('POS') else 'NEGative'}")
    if "trig_level" in preset:
        scope.write(f":TRIGger:EDGE:LEVel {preset['trig_level']}")
    scope.write(":TRIGger:EDGE:SOURce CHAN1")
    for ch in (1, 2):
        scale = preset.get(f"ch{ch}_scale")
        offs = preset.get(f"ch{ch}_offset")
        if scale is not None or offs is not None:
            _force_chan(
                scope,
                ch,
                float(scale) if scale is not None else None,
                float(offs) if offs is not None else None,
            )
    scope.write(":RUN")
    scope.write(":SYSTem:KEY:PRESs MOFF")


def _query_stat(scope, stat: str, item: str, source: str) -> float | None:
    try:
        raw = scope.query(f":MEASure:STATistic:ITEM? {stat},{item},{source}").strip()
        val = float(raw)
        if abs(val) > 1e12:
            return None
        return val
    except Exception as exc:
        if is_visa_poison(exc):
            raise
        return None


def setup_slew_measure(
    scope,
    *,
    slew_item: str,
    slew_ch: str = "CHAN2",
    vpp_ch: str = "CHAN1",
) -> None:
    """Enable on-screen measure + statistic table for slew + input Vpp."""
    scope.write(":MEASure:CLEar ALL")
    time.sleep(0.2)
    scope.write(f":MEASure:ITEM {slew_item},{slew_ch}")
    scope.write(f":MEASure:ITEM VPP,{vpp_ch}")
    scope.write(f":MEASure:STATistic:ITEM {slew_item},{slew_ch}")
    scope.write(f":MEASure:STATistic:ITEM VPP,{vpp_ch}")
    scope.write(":MEASure:STATistic:DISPlay ON")


def setup_settling_photo(scope, *, ax_px: int, bx_px: int) -> None:
    """Vpp1 + Vmax2 stats and TIME cursors — matches operator settling golden."""
    scope.write(":MEASure:CLEar ALL")
    time.sleep(0.15)
    scope.write(":MEASure:ITEM VPP,CHAN1")
    scope.write(":MEASure:ITEM VMAX,CHAN2")
    scope.write(":MEASure:STATistic:ITEM VPP,CHAN1")
    scope.write(":MEASure:STATistic:ITEM VMAX,CHAN2")
    scope.write(":MEASure:STATistic:DISPlay ON")
    scope.write(":CURSor:MODE MANual")
    scope.write(":CURSor:MANual:TYPE TIME")
    scope.write(":CURSor:MANual:SOURce CHANnel1")
    scope.write(":CURSor:MANual:TUNit SECond")
    scope.write(f":CURSor:MANual:CAX {int(ax_px)}")
    scope.write(f":CURSor:MANual:CBX {int(bx_px)}")


def wait_slew_statistics(
    scope,
    slew_item: str,
    *,
    slew_ch: str = "CHAN2",
    min_count: int = 80,
    timeout_s: float = 6.0,
    settle_s: float = 1.5,
) -> None:
    """Let statistic engine accumulate before screenshot / readout."""
    try:
        scope.write(":RUN")
    except Exception:
        pass
    time.sleep(settle_s)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        cnt = _query_stat(scope, "COUNt", slew_item, slew_ch)
        if cnt is not None and cnt >= min_count:
            time.sleep(0.4)
            return
        time.sleep(0.25)
    time.sleep(0.5)
    cnt = _query_stat(scope, "COUNt", slew_item, slew_ch)
    if cnt is None or cnt < 1:
        raise RuntimeError(
            f"slew {slew_item} Cnt=0 after {timeout_s:.0f}s - scope not acquiring "
            "(RUN/trigger/AWG, or probe on GND)"
        )


def read_measure_statistics(
    scope,
    item: str,
    source: str,
    *,
    as_mv_per_s: bool = False,
) -> dict[str, Any]:
    """Read CUR/AVG/MAX/MIN/DEV/CNT for one measure item."""
    stats: dict[str, Any] = {}
    for key in STAT_KEYS:
        val = _query_stat(scope, key, item, source)
        if val is None:
            continue
        stats[key.lower()] = val
        if as_mv_per_s:
            stats[f"{key.lower()}_mv_per_s"] = val / 1e6
            stats[f"{key.lower()}_v_per_us"] = val * 1e-6
    return stats


__all__ = [
    "is_visa_poison",
    "capture_jpeg",
    "capture_scope_png",
    "apply_scope_preset",
    "apply_scope_manual",
    "setup_slew_measure",
    "setup_settling_photo",
    "wait_slew_statistics",
    "read_measure_statistics",
    "measure_single",
    "scope_setup",
    "set_threshold",
]
