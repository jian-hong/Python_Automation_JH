"""Slew Rate — 1 Vpp + 2 Vpp @ 1 kHz, statistics on-screen, JSON/TXT in graphs/."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from ate.core.paths import graph_dir
from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams
from ate.drivers.mso5072 import (
    apply_scope_manual,
    capture_jpeg,
    read_measure_statistics,
    setup_slew_measure,
    wait_slew_statistics,
)
from ate.reporting.lab_report import ensure_screenshot_dir, save_named_screenshot

MYT = timezone(timedelta(hours=8))

# Photo lock = 31 Jul / 7 Aug goldens (201 ns, 200 mV +208 / -208 @ 1 Vpp).
# LabAutomation test_sr used 2 Vpp, 500 mV, CH1 -20 mV, delay 400 ns, AUToscale.
# Keep these numbers: they match the accepted lab JPEGs, not the 14.7 offsets.

SLEW_POS_PRESET = {
    "timebase": 200e-9,
    "ch1_scale": 0.2,
    "ch1_offset": 0.208,
    "ch2_scale": 0.2,
    "ch2_offset": -0.208,
    "time_offset": 201e-9,
    "trig_level": -0.00846,
    "trig_slope": "POS",
}

SLEW_NEG_PRESET = {
    "timebase": 200e-9,
    "ch1_scale": 0.2,
    "ch1_offset": -0.184,
    "ch2_scale": 0.2,
    "ch2_offset": 0.06,
    "time_offset": 520e-9,
    "trig_level": 0.1,
    "trig_slope": "NEG",
}

VPP_LEVELS = (1.0, 2.0)
FREQ_HZ = 1000.0

SLEW_FIXED_STEPS = [
    {"id": "pos_1v", "label": "SR+ @ 1 Vpp", "polarity": "positive", "vpp_v": 1.0},
    {"id": "neg_1v", "label": "SR− @ 1 Vpp", "polarity": "negative", "vpp_v": 1.0},
    {"id": "pos_2v", "label": "SR+ @ 2 Vpp", "polarity": "positive", "vpp_v": 2.0},
    {"id": "neg_2v", "label": "SR− @ 2 Vpp", "polarity": "negative", "vpp_v": 2.0},
]


def _preset_for_vpp(base: dict, vpp: float) -> dict:
    """1 Vpp keeps Eugene 200 mV/div offsets; 2 Vpp widens to 500 mV/div."""
    p = dict(base)
    if vpp < 2.0:
        return p
    scale = 2.5
    p["ch1_scale"] = 0.5
    p["ch2_scale"] = 0.5
    p["ch1_offset"] = float(base["ch1_offset"]) * scale
    p["ch2_offset"] = float(base["ch2_offset"]) * scale
    return p


def _vpp_tag(vpp: float) -> str:
    return f"{int(vpp)}V" if vpp == int(vpp) else f"{vpp}V".replace(".", "p")


def _emit(params: RunParams, step_id: str, status: str, message: str) -> None:
    hook: Optional[Callable[..., None]] = getattr(params, "progress_hook", None)
    if hook:
        hook(step_id, status, message)


def _save_run_artifacts(
    graph_out: Path,
    *,
    unit: int,
    channel: str,
    vcc: float,
    batch_id: str,
    records: list[dict[str, Any]],
) -> tuple[Path, Path]:
    graph_out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
    json_path = graph_out / f"SlewRate_{unit}_{batch_id}.json"
    txt_path = graph_out / f"SlewRate_{unit}_{batch_id}.txt"

    units_block = {
        "slew_scope_raw": "V/s (Rigol PSLewrate/NSLewrate)",
        "slew_mv_per_s": "MV/s (display units, numerically = V/µs)",
        "slew_v_per_us": "V/µs",
        "vpp": "V",
    }

    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    else:
        payload = {}

    if not payload:
        payload = {
            "test": "SlewRate",
            "dut": unit,
            "vcc_v": vcc,
            "freq_hz": FREQ_HZ,
            "fixed_steps": SLEW_FIXED_STEPS,
            "run_batch_id": batch_id,
            "units": units_block,
            "channels": {},
        }

    channels = payload.setdefault("channels", {})
    channels[channel] = {
        "captured_at": ts,
        "results": records,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"Slew Rate — DUT {unit}  batch={batch_id}  VCC={vcc} V  f={FREQ_HZ:.0f} Hz",
        "",
    ]
    for ch_key, ch_data in channels.items():
        lines.append(f"=== {ch_key}  (captured {ch_data.get('captured_at', '')}) ===")
        for rec in ch_data.get("results", []):
            pol = rec["polarity"]
            vpp = rec["vpp_v"]
            sr = rec["slew"]
            vpp1 = rec.get("vpp_ch1", {})
            label = "SR+" if pol == "positive" else "SR-"
            lines.append(f"--- {pol} @ {vpp} Vpp ---")
            if sr.get("current_mv_per_s") is not None:
                lines.append(
                    f"  {label} (MV/s)  Cur={sr['current_mv_per_s']:.4f}  "
                    f"Avg={sr.get('averages_mv_per_s', 0):.4f}  "
                    f"Max={sr.get('maximum_mv_per_s', 0):.4f}  "
                    f"Min={sr.get('minimum_mv_per_s', 0):.4f}  "
                    f"Dev={sr.get('deviation_mv_per_s', 0):.4f}  "
                    f"Cnt={int(sr.get('count', 0))}"
                )
            else:
                lines.append(f"  {label} — no valid statistics")
            if vpp1.get("current") is not None and abs(vpp1["current"]) < 100:
                lines.append(
                    f"  Vpp CH1 (V) Cur={vpp1['current']:.4f}  Avg={vpp1.get('averages', 0):.4f}"
                )
            shot = rec.get("screenshot", "")
            lines.append(f"  Screenshot: {Path(shot).name if shot else ''}")
            lines.append("")

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, txt_path


def _measure_edge(
    scope,
    *,
    preset: dict,
    slew_item: str,
    polarity: str,
    vpp: float,
    unit: int,
    channel: str,
    shot_dir: Path,
    ts: str,
    step_id: str,
    params: RunParams,
) -> dict[str, Any]:
    tag = _vpp_tag(vpp)
    variant = f"{'POS' if polarity == 'positive' else 'NEG'}_{tag}"
    tmp = shot_dir / f"_tmp_slew_{variant}_{channel}_U{unit}_{ts}.jpg"

    _emit(params, step_id, "running", f"{variant} {channel} — setup scope")
    from scope_setup import recover_scope_session

    recover_scope_session(scope, run=True)
    edge_preset = _preset_for_vpp(preset, vpp)
    apply_scope_manual(scope, edge_preset)
    time.sleep(0.4)
    setup_slew_measure(scope, slew_item=slew_item)
    _emit(params, step_id, "running", f"{variant} {channel} — accumulating stats")
    wait_slew_statistics(scope, slew_item, min_count=80, timeout_s=6.0, settle_s=1.8)

    slew_stats = read_measure_statistics(scope, slew_item, "CHAN2", as_mv_per_s=True)
    vpp_stats = read_measure_statistics(scope, "VPP", "CHAN1", as_mv_per_s=False)
    vin = vpp_stats.get("current")
    if vin is None or abs(float(vin)) < 0.4 * vpp:
        raise RuntimeError(
            f"{variant} CH1 Vpp={vin} expected ~{vpp} V "
            "(probe on GND / wrong channel / AWG off)"
        )

    # Measure:ITEM opens the right-hand menu; original Eugene SR MOFF before the photo.
    try:
        scope.write(":SYSTem:KEY:PRESs MOFF")
    except Exception:
        pass
    time.sleep(0.25)
    _emit(params, step_id, "running", f"{variant} {channel} — capture JPEG")
    capture_jpeg(scope, tmp)
    final = save_named_screenshot(
        "SlewRate",
        unit=unit,
        variant=variant,
        source_bytes_path=tmp,
        channel=channel,
    )
    try:
        if tmp.exists() and tmp != final:
            tmp.unlink()
    except Exception:
        pass

    avg = slew_stats.get("averages_mv_per_s")
    _emit(
        params,
        step_id,
        "done",
        f"{variant} {channel} Avg={avg:.4f} MV/s" if avg is not None else f"{variant} done",
    )

    return {
        "step_id": step_id,
        "polarity": polarity,
        "vpp_v": vpp,
        "freq_hz": FREQ_HZ,
        "channel": channel,
        "slew_item": slew_item,
        "slew": slew_stats,
        "vpp_ch1": vpp_stats,
        "screenshot": str(final),
        "screenshot_name": Path(final).name,
    }


def _run(instr, params: RunParams):
    from configurations import current_limit
    from generator_setup import setup_square
    from psu_setup import power_on_protected

    psu, gen, scope = instr.psu, instr.gen, instr.scope
    vcc = params.vcc
    unit = params.unit_index
    channel = (params.channel or "CHA").upper()
    shot_dir = ensure_screenshot_dir("SlewRate", unit)
    graph_out = graph_dir("SlewRate", unit)
    ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
    batch_id = (params.run_batch_id or ts).strip() or ts
    shots: list[str] = []
    records: list[dict[str, Any]] = []

    try:
        power_on_protected(psu, 1, vcc / 2, current_limit)
        time.sleep(0.5)
        power_on_protected(psu, 2, vcc / 2, current_limit)
        time.sleep(0.5)

        for step in SLEW_FIXED_STEPS:
            vpp = float(step["vpp_v"])
            pol = step["polarity"]
            step_id = str(step["id"])
            setup_square(gen, 1, FREQ_HZ, vpp, 0)
            time.sleep(0.8)

            if pol == "positive":
                rec = _measure_edge(
                    scope,
                    preset=SLEW_POS_PRESET,
                    slew_item="PSLewrate",
                    polarity="positive",
                    vpp=vpp,
                    unit=unit,
                    channel=channel,
                    shot_dir=shot_dir,
                    ts=ts,
                    step_id=step_id,
                    params=params,
                )
            else:
                rec = _measure_edge(
                    scope,
                    preset=SLEW_NEG_PRESET,
                    slew_item="NSLewrate",
                    polarity="negative",
                    vpp=vpp,
                    unit=unit,
                    channel=channel,
                    shot_dir=shot_dir,
                    ts=ts,
                    step_id=step_id,
                    params=params,
                )
            records.append(rec)
            shots.append(rec["screenshot"])

        got = {str(r.get("step_id")) for r in records}
        need = {str(s["id"]) for s in SLEW_FIXED_STEPS}
        if got != need:
            raise RuntimeError(f"slew missing steps {sorted(need - got)} (need POS/NEG @ 1V and 2V)")

        json_path, txt_path = _save_run_artifacts(
            graph_out,
            unit=unit,
            channel=channel,
            vcc=vcc,
            batch_id=batch_id,
            records=records,
        )

        def _sr_mv(rec: dict) -> float | None:
            return rec.get("slew", {}).get("averages_mv_per_s")

        pos_1v = next((r for r in records if r["step_id"] == "pos_1v"), {})
        pos_2v = next((r for r in records if r["step_id"] == "pos_2v"), {})
        neg_1v = next((r for r in records if r["step_id"] == "neg_1v"), {})
        neg_2v = next((r for r in records if r["step_id"] == "neg_2v"), {})

        return {
            "summary": (
                f"{channel} SR+ @1V={_sr_mv(pos_1v) or 0:.4f}  "
                f"@2V={_sr_mv(pos_2v) or 0:.4f}  "
                f"SR- @1V={_sr_mv(neg_1v) or 0:.4f}  "
                f"@2V={_sr_mv(neg_2v) or 0:.4f} MV/s"
            ),
            "channel": channel,
            "SR_positive_1Vpp_MV_s": _sr_mv(pos_1v),
            "SR_positive_2Vpp_MV_s": _sr_mv(pos_2v),
            "SR_negative_1Vpp_MV_s": _sr_mv(neg_1v),
            "SR_negative_2Vpp_MV_s": _sr_mv(neg_2v),
            "screenshots": shots,
            "data_json": str(json_path),
            "data_txt": str(txt_path),
            "run_batch_id": batch_id,
            "lab_sheet": "Slew Rate",
            "fixed_steps": SLEW_FIXED_STEPS,
        }
    finally:
        # PSU/AWG stay up for VISA retry. Runner _safe_idle is the only off-ramp.
        try:
            scope.write(":MEASure:CLEar ALL")
            scope.write(":MEASure:STATistic:DISPlay OFF")
        except Exception:
            pass


register(
    TestSpec(
        id="slew",
        label="Slew Rate",
        required_instruments=frozenset({"MSO", "PSU", "AWG"}),
        fixture_mode="BUFFER",
        lab_sheet="Slew Rate",
        run=_run,
        notes="1+2 Vpp @1kHz per channel; stats on-screen; graphs JSON+TXT",
        scope_preset={"timebase": 200e-9},
        fixed_steps=SLEW_FIXED_STEPS,
        dual_channel=True,
    )
)
