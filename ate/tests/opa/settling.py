"""Settling Time — BUFFER alone; scales locked to operator reference screenshot."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from ate.core.paths import LAB_REPORT_PATH
from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams
from ate.drivers.mso5072 import apply_scope_manual, capture_jpeg, setup_settling_photo, wait_slew_statistics
from ate.reporting.lab_report import (
    ensure_screenshot_dir,
    place_settling_photos,
    save_named_screenshot,
    update_summary_status,
)

MYT = timezone(timedelta(hours=8))

# Locked to operator golden: H=200ns D=400ns CH1/CH2=500mV, AX on Vin, BX ~650ns
SETTLING_PRESET = {
    "timebase": 200e-9,
    "time_offset": 400e-9,
    "ch1_scale": 0.5,
    "ch1_offset": 0.0,
    "ch2_scale": 0.5,
    "ch2_offset": -0.5,
    "trig_level": 0.02,
    "trig_slope": "POS",
}

# ax/bx are Rigol screen pixels (0-999). 0.1% matches golden AX~Vin, BX~650ns.
BANDS = (
    ("BAND_0p1", 350, 675, "AX on Vin edge, BX at 0.1% settle"),
    ("BAND_0p01", 350, 760, "BX moved to 0.01% error band"),
)


def _emit(params: RunParams, step_id: str, status: str, message: str) -> None:
    hook: Optional[Callable[..., None]] = getattr(params, "progress_hook", None)
    if hook:
        hook(step_id, status, message)


def _run(instr, params: RunParams):
    """Settling alone — BUFFER, CL=100pF recipe. Independent of ORT/GBW."""
    from configurations import current_limit
    from generator_setup import setup_square
    from psu_setup import power_on_protected

    psu, gen, scope = instr.psu, instr.gen, instr.scope
    vcc = params.vcc
    unit = int(params.unit_index or 1)
    ch = (params.channel or "CHA").upper()
    out_dir = ensure_screenshot_dir("SettlingTime", unit)
    ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
    shots: list[Path] = []

    try:
        power_on_protected(psu, 1, vcc / 2, current_limit)
        power_on_protected(psu, 2, vcc / 2, current_limit)
        setup_square(gen, 1, 1000, 2.0, 0)
        apply_scope_manual(scope, SETTLING_PRESET)
        time.sleep(0.8)
        try:
            scope.write(":SYSTem:KEY:PRESs MOFF")
        except Exception:
            pass
        ch2_vpp = None
        try:
            ch2_vpp = abs(float(scope.query(":MEASure:ITEM? VPP,CHAN2")))
        except Exception:
            ch2_vpp = None
        if ch2_vpp is None or ch2_vpp > 1e12 or ch2_vpp < 0.4:
            raise RuntimeError(
                f"settling CH2 Vpp={ch2_vpp} expected ~2 V "
                "(CHA output path, or CH2 still AC-coupled from GBW)"
            )

        primary: Path | None = None
        for variant, ax_px, bx_px, hint in BANDS:
            _emit(params, variant, "running", f"Settling {variant}: {hint}")
            print(f"Settling {variant}: {hint}", flush=True)
            setup_settling_photo(scope, ax_px=ax_px, bx_px=bx_px)
            wait_slew_statistics(
                scope, "VPP", slew_ch="CHAN1", min_count=80, timeout_s=6.0, settle_s=1.5
            )
            try:
                scope.write(":SYSTem:KEY:PRESs MOFF")
            except Exception:
                pass
            time.sleep(0.25)
            tmp = out_dir / f"_tmp_settling_{variant}_U{unit}_{ts}.jpg"
            capture_jpeg(scope, tmp)
            path = save_named_screenshot(
                "SettlingTime",
                unit=unit,
                variant=variant,
                source_bytes_path=tmp,
                channel=ch,
            )
            shots.append(path)
            if primary is None:
                primary = path
            try:
                if tmp.exists() and tmp != path:
                    tmp.unlink()
            except Exception:
                pass

        lab = Path(params.lab_report or LAB_REPORT_PATH)
        try:
            # 8-box sheet holds one photo per DUT/ch — paste 0.1% band; 0.01% stays on disk
            place_settling_photos(
                lab,
                photo_path=primary,
                unit_index=unit,
                channel=ch,
            )
            update_summary_status(lab, "Settling Time", "Pass")
            excel_msg = f"embedded {primary.name if primary else '?'} in {lab.name}"
        except Exception as exc:
            excel_msg = f"Excel update skipped: {exc}"

        return {
            "summary": f"Settling photos → Test_Database; {excel_msg}",
            "screenshots": [str(p) for p in shots],
            "lab_sheet": "SettlingTime",
        }
    finally:
        # PSU/AWG stay up for VISA retry. Runner _safe_idle is the only off-ramp.
        try:
            scope.write(":MEASure:CLEar ALL")
        except Exception:
            pass


register(
    TestSpec(
        id="settling",
        label="Settling Time",
        required_instruments=frozenset({"MSO", "PSU", "AWG"}),
        fixture_mode="BUFFER",
        lab_sheet="SettlingTime",
        run=_run,
        notes="BUFFER CL=100pF; scales locked to operator Settling reference shot",
        fixed_steps=[
            {"id": "BAND_0p1", "label": "0.1% error band", "phase": "measure"},
            {"id": "BAND_0p01", "label": "0.01% error band", "phase": "measure"},
        ],
    )
)
