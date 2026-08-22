"""GBW — LabAutomation_14.7 / PythonAutomation measure_gbw wrapper."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ate.core.param_defaults import GBW_FIXED_STEPS
from ate.core.paths import graph_dir
from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams
from ate.drivers.mso5072 import capture_jpeg
from ate.reporting.lab_report import ensure_screenshot_dir, save_named_screenshot

MYT = timezone(timedelta(hours=8))


def _save_gbw_json(
    graph_out: Path,
    *,
    unit: int,
    channel: str,
    batch_id: str,
    payload: dict[str, Any],
) -> Path:
    graph_out.mkdir(parents=True, exist_ok=True)
    json_path = graph_out / f"GBW_{unit}_{batch_id}.json"

    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    else:
        existing = {}

    channels = existing.get("channels") if isinstance(existing.get("channels"), dict) else {}
    channels[channel] = payload

    doc = {
        "test": "GBW",
        "dut": unit,
        "run_batch_id": batch_id,
        "units": {
            "vpp": "mV",
            "freq": "Hz / kHz",
            "gbw": "MHz",
        },
        "channels": channels,
    }
    if isinstance(existing, dict):
        for key in ("vcc_v", "gain", "rf", "ri", "run_label", "updated_at"):
            if key in existing:
                doc[key] = existing[key]
    doc.update(
        {
            "vcc_v": payload.get("vcc_v"),
            "gain": payload.get("gain"),
            "rf": payload.get("rf"),
            "ri": payload.get("ri"),
            "run_label": payload.get("run_label"),
            "updated_at": datetime.now(MYT).isoformat(timespec="seconds"),
        }
    )

    json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return json_path


def _run(instr, params: RunParams):
    from ate.drivers.mso5072 import is_visa_poison
    from opa_tests import measure_gbw
    from scope_setup import recover_scope_session

    gain = float(params.gain) if params.gain else 11.0
    amp = float(params.amp_vpp) if params.amp_vpp else 0.05
    unit = int(params.unit_index or 1)
    channel = (params.channel or "CHA").upper()
    shot_dir = ensure_screenshot_dir("GBW", unit)
    graph_out = graph_dir("GBW", unit)
    ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
    batch_id = (params.run_batch_id or ts).strip() or ts

    def shot_cb(scope, variant: str = "1kHz_baseline") -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(variant))
        tmp = shot_dir / f"_tmp_gbw_{unit}_{channel}_{safe}.jpg"
        try:
            capture_jpeg(scope, tmp, timeout_ms=8000)
        except Exception as exc:
            print(f"GBW screenshot capture failed ({variant}): {exc}", flush=True)
            try:
                recover_scope_session(scope, clear=True, run=True)
            except Exception:
                pass
            return ""
        if not tmp.exists() or tmp.stat().st_size < 100:
            return ""
        final = save_named_screenshot(
            "GBW",
            unit=unit,
            variant=safe[:40] or "capture",
            source_bytes_path=Path(tmp),
            channel=channel,
        )
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        print(f"GBW screenshot → {final}", flush=True)
        return str(final)

    def _call_measure(*, with_shots: bool):
        return measure_gbw(
            instr,
            vcc=params.vcc,
            amp=amp,
            gain=gain,
            current_limit_a=params.current_limit_a,
            debug=True,
            progress_cb=(
                (lambda step, msg: params.progress_hook(step, "running", msg))
                if params.progress_hook
                else None
            ),
            pause_cb=params.pause_hook,
            shot_cb=shot_cb if with_shots else None,
        )

    raw = None
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            if instr.scope is not None:
                recover_scope_session(instr.scope)
            # First try with screenshots; retry without if VISA dies mid-run
            raw = _call_measure(with_shots=(attempt == 0))
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            visaish = is_visa_poison(msg)
            print(
                f"GBW attempt {attempt + 1} failed (DUT {unit} {channel}): {exc}",
                flush=True,
            )
            try:
                from generator_setup import park_generator_idle
                from psu_setup import power_off

                if instr.gen is not None:
                    park_generator_idle(instr.gen)
                if instr.psu is not None:
                    power_off(instr.psu)
            except Exception:
                pass
            if instr.scope is not None:
                try:
                    from scope_setup import park_scope_idle

                    park_scope_idle(instr.scope, clear=True)
                except Exception:
                    pass
            if not visaish or attempt == 1:
                raise
            print("GBW retrying once after VISA recover (screenshots off)...", flush=True)

    if last_exc is not None:
        raise last_exc
    if raw is None:
        raise RuntimeError("GBW measurement failed")
    gbw_mhz = raw["GBW_MHz"] if isinstance(raw, dict) else float(raw)
    net = ""
    if params.rf and params.ri:
        net = f" RF={params.rf} RI={params.ri}"
    label = f" [{params.run_label}]" if params.run_label else ""
    av = raw.get("Av", "?")

    json_payload: dict[str, Any] = {
        "vcc_v": params.vcc,
        "gain": gain,
        "rf": params.rf,
        "ri": params.ri,
        "run_label": params.run_label,
        "baseline_1kHz": {
            "freq_Hz": raw.get("baseline_freq_Hz", 1000.0),
            "vpp_in_mV": raw.get("Vpp_IN_mV"),
            "vout_mV": raw.get("VOUT_1k_mV"),
            "av": raw.get("Av"),
            "target_vout_707_mV": raw.get("VOUT_707_mV"),
            "target_ratio": raw.get("target_ratio", 0.707),
        },
        "f3db": {
            "freq_Hz": raw.get("F_3dB_Hz"),
            "freq_kHz": raw.get("F_3dB_kHz"),
            "vout_mV": raw.get("VOUT_f3db_mV"),
        },
        "gbw_MHz": gbw_mhz,
        "calculation": raw.get("calculation"),
        "sweep_log": raw.get("sweep_log") or [],
    }
    shots = raw.get("screenshots") or (
        [raw["screenshot"]] if raw.get("screenshot") else []
    )
    if shots:
        json_payload["screenshots"] = shots
        json_payload["screenshot"] = shots[-1]

    json_path = _save_gbw_json(
        graph_out,
        unit=unit,
        channel=channel,
        batch_id=batch_id,
        payload=json_payload,
    )
    print(f"GBW JSON → {json_path}", flush=True)

    out = {
        "summary": (
            f"GBW={gbw_mhz:.3f} MHz Av={av} "
            f"f-3dB={raw.get('F_3dB_kHz', '?')} kHz "
            f"VOUT@1k={raw.get('VOUT_1k_mV', '?')} mV{net}{label}"
        ),
        "GBW_MHz": gbw_mhz,
        "F_3dB_kHz": raw.get("F_3dB_kHz"),
        "VOUT_1k_mV": raw.get("VOUT_1k_mV"),
        "VOUT_707_mV": raw.get("VOUT_707_mV"),
        "VOUT_f3db_mV": raw.get("VOUT_f3db_mV"),
        "Vpp_IN_mV": raw.get("Vpp_IN_mV"),
        "Av": raw.get("Av"),
        "gain": gain,
        "rf": params.rf,
        "ri": params.ri,
        "run_label": params.run_label,
        "lab_sheet": "GBW",
        "json_path": str(json_path),
        "baseline_1kHz": json_payload["baseline_1kHz"],
        "f3db": json_payload["f3db"],
        "sweep_log": json_payload["sweep_log"],
        "calculation": json_payload["calculation"],
    }
    if shots:
        out["screenshot"] = shots[-1]
        out["screenshots"] = shots
    return out


register(
    TestSpec(
        id="gbw",
        label="Gain Bandwidth Product",
        required_instruments=frozenset({"MSO", "PSU", "AWG"}),
        fixture_mode="G11",
        lab_sheet="GBW",
        run=_run,
        notes="G11 board locked — 50 mVpp @ 1 kHz, sweep to Vout×0.707",
        fixed_steps=GBW_FIXED_STEPS,
        dual_channel=True,
    )
)
