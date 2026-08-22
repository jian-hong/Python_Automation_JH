"""Per-test bench defaults + optional gain-network profiles (GBW comparison runs)."""
from __future__ import annotations

import re
from typing import Any

from ate.fixture.modes import load_fixture_catalog

_OHM_RE = re.compile(r"^([\d.]+)\s*([kKmM]?)\s*[ΩΩ]?$|^(short|open)$", re.I)

# GBW operator + measure sequence (shown in UI like slew fixed_steps)
GBW_FIXED_STEPS = [
    {"id": "cfg_g11", "label": "Confirm G11 board (RF=10k RI=1k)", "phase": "operator"},
    {"id": "awg_1k", "label": "AWG 50 mVpp @ 1 kHz · fit CH1/CH2 on screen", "phase": "setup"},
    {"id": "baseline", "label": "Statistics ON — Freq1 Vpp1 Vpp2 · target = Vout×0.707", "phase": "measure"},
    {"id": "shot_1k", "label": "Screenshot @ 1 kHz (stats on, measure menu off)", "phase": "measure"},
    {"id": "coarse", "label": "Coarse +100 kHz (100, 200, 300 kHz…) until Vout <= target", "phase": "measure"},
    {"id": "fine", "label": "Refine +10 k / +1 k / +100 / +10 Hz", "phase": "measure"},
    {"id": "shot_f3db", "label": "Screenshot @ f−3dB (stats on, measure menu off)", "phase": "measure"},
    {"id": "gbw_calc", "label": "GBW = Av × f−3dB", "phase": "done"},
]

# Auto run labels per profile key
GBW_RUN_LABELS = {
    "default": "G11_1k_10k",
    "alt_100r_1k": "G11_100R_1k",
}

TEST_DEFAULTS: dict[str, dict[str, Any]] = {
    "gbw": {
        "vcc": 5.0,
        "amp_vpp": 0.05,
        "freq_hz": 1000.0,
        "n_repeats": 1,
        "channels": ["CHA"],
        "fixture_mode": "G11",
        "gain_profile": "default",
    },
    "slew": {
        "vcc": 5.0,
        "amp_vpp": 1.0,
        "freq_hz": 1000.0,
        "n_repeats": 1,
        "channels": ["CHA", "CHB"],
        "fixture_mode": "BUFFER",
    },
    "ort": {
        "vcc": 5.0,
        "amp_vpp": 4.0,
        "freq_hz": 250000.0,
        "n_repeats": 1,
        "channels": ["CHA", "CHB"],
        "fixture_mode": "G_NEG100",
    },
    "vos_sweep": {
        "vcc": 5.0,
        "amp_vpp": 0.004,
        "freq_hz": 500.0,
        "n_repeats": 1,
        "channels": ["CHA"],
        "fixture_mode": "G201",
    },
    "ac_gain_check": {
        "vcc": 5.0,
        "amp_vpp": 0.004,
        "freq_hz": 500.0,
        "n_repeats": 3,
        "channels": ["CHA"],
        "fixture_mode": "G201",
    },
    "ac_vin_sweep": {
        "vcc": 5.0,
        "amp_vpp": 0.004,
        "freq_hz": 500.0,
        "n_repeats": 1,
        "channels": ["CHA"],
        "fixture_mode": "G201",
    },
}

# PSU golden rules (LabAutomation / opa_tests convention)
PSU_GOLDEN = {
    "current_limit_a": 0.10,
    "ovp_margin_v": 0.3,
    "ocp_margin_a": 0.1,
}


def parse_ohm(value: str) -> float:
    s = str(value or "").strip().lower()
    if s in ("short", "0", "0ohm"):
        return 0.0
    if s in ("open", "inf"):
        raise ValueError(f"Cannot parse open RI as numeric: {value}")
    m = _OHM_RE.match(s.replace("ohm", "").replace("ω", ""))
    if not m:
        raise ValueError(f"Bad resistor value: {value!r}")
    if m.group(3):
        return 0.0 if m.group(3) == "short" else float("inf")
    num = float(m.group(1))
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        num *= 1e3
    elif suffix == "m":
        num *= 1e6
    return num


def noninv_gain(rf: str, ri: str) -> float:
    ri_v = parse_ohm(ri)
    if ri_v <= 0:
        raise ValueError(f"RI must be > 0 for gain calc: {ri!r}")
    rf_v = parse_ohm(rf)
    return 1.0 + rf_v / ri_v


def gain_profiles_for_mode(mode: str, part: str = "rs622") -> dict[str, dict[str, Any]]:
    catalog = load_fixture_catalog(part)
    entry = catalog.get(mode) or catalog.get(str(mode).upper()) or {}
    profiles = dict(entry.get("gain_profiles") or {})
    if not profiles:
        rf = entry.get("rf")
        ri = entry.get("ri")
        g = entry.get("gain")
        if rf and ri and g is not None:
            profiles["default"] = {
                "label": entry.get("label") or mode,
                "rf": rf,
                "ri": ri,
                "gain": g,
            }
    return profiles


def resolve_gain_profile(
    mode: str,
    profile_key: str,
    part: str = "rs622",
) -> dict[str, Any]:
    profiles = gain_profiles_for_mode(mode, part)
    key = profile_key if profile_key in profiles else "default"
    prof = dict(profiles.get(key) or profiles.get("default") or {})
    rf = str(prof.get("rf") or "")
    ri = str(prof.get("ri") or "")
    gain = prof.get("gain")
    if gain is None and rf and ri:
        try:
            gain = noninv_gain(rf, ri)
        except ValueError:
            gain = None
    prof["gain"] = float(gain) if gain is not None else None
    prof["profile_key"] = key
    return prof


def merged_defaults(test_ids: list[str]) -> dict[str, Any]:
    """Merge defaults for selected tests; first test wins on conflict."""
    out: dict[str, Any] = {
        "vcc": 5.0,
        "freq_hz": 500.0,
        "amp_vpp": 0.004,
        "n_repeats": 3,
        "channels": ["CHA", "CHB"],
        "current_limit_a": PSU_GOLDEN["current_limit_a"],
    }
    for tid in test_ids:
        d = TEST_DEFAULTS.get(tid)
        if d:
            out.update(d)
    return out


def catalog_for_ui(part: str = "rs622") -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for mode in ("G11",):
        rows = []
        for key, prof in gain_profiles_for_mode(mode, part).items():
            row = dict(prof)
            row["key"] = key
            row["mode"] = mode
            if row.get("gain") is None and row.get("rf") and row.get("ri"):
                try:
                    row["gain"] = noninv_gain(str(row["rf"]), str(row["ri"]))
                except ValueError:
                    pass
            rows.append(row)
        if rows:
            profiles[mode] = rows
    return {
        "tests": TEST_DEFAULTS,
        "psu_golden": PSU_GOLDEN,
        "gain_profiles": profiles,
        "gbw_steps": GBW_FIXED_STEPS,
        "gbw_run_labels": GBW_RUN_LABELS,
    }
