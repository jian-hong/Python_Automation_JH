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

# OPA measurement timing (family-local; bodies may keep literals equivalent)
_OPA_TIMEOUT_S = 6.0
_OPA_SETTLE_SLEW_S = 1.8
_OPA_SETTLE_DEFAULT_S = 1.5

# Logic bench defaults (vcc etc. for wraps; no OPA gain/GBW chrome)
LOGIC_TEST_DEFAULTS: dict[str, dict[str, Any]] = {
    "tp": {"vcc": 5.0},
    "tidle": {"vcc": 5.0},
    "tdis": {"vcc": 5.0},
    "ten": {"vcc": 5.0},
    "supply_current": {"vcc": 5.0},
    "output_voltage": {"vcc": 5.0},
    "cap_load": {},
    # Ariff / RS1G08 DC slots (A09/A12) — part yaml may override vcc
    "delta_supply_current": {"vcc": 1.65},
    "off_current": {"vcc": 1.65},
    "input_thresholds": {"vcc": 1.65},
    "ioff_leakage": {"vcc": 1.65},
    "input_leakage_sweep": {"vcc": 1.65},
    "supply_current_sweep": {"vcc": 1.65},
    "vih_vil": {"vcc": 1.65},
    "voh_load": {"vcc": 1.65},
    "vol_load": {"vcc": 1.65},
    # Path B Logic DC (product_model YAML)
    "input_threshold": {"vcc": 1.65},
    "vth": {"vcc": 1.65},
    "delta_icc": {"vcc": 1.65},
    "ii": {"vcc": 1.65},
    "ioz": {"vcc": 1.65},
    # RS0204 dual-rail (vcc = VCCA; vccb from part yaml)
    "vih": {"vcc": 1.8, "vccb": 3.3},
    "vil": {"vcc": 1.8, "vccb": 3.3},
    "voh": {"vcc": 1.8},
    "vol": {"vcc": 1.8},
    "icc": {"vcc": 1.8},
    "il": {"vcc": 1.8, "vccb": 3.3},
    "tpd": {"vcc": 1.8, "vccb": 3.3, "freq_hz": 400000.0},
    "tp_rs0204": {"vcc": 1.8, "vccb": 3.3, "freq_hz": 400000.0},
    "tsu": {"vcc": 1.8, "vccb": 3.3},
    "th": {"vcc": 1.8, "vccb": 3.3},
    "fmax": {"vcc": 1.8, "vccb": 3.3},
    "tr": {"vcc": 1.8, "vccb": 3.3},
    "tf": {"vcc": 1.8, "vccb": 3.3},
    "tsk": {"vcc": 1.8, "vccb": 3.3},
    "cpd": {"vcc": 1.8, "vccb": 3.3},
    "tw": {"vcc": 1.8, "vccb": 3.3},
}

LIM_TEST_DEFAULTS: dict[str, dict[str, Any]] = {
    "iplus": {"vcc": 5.0},
    "leakage_off": {"vcc": 5.0},
    "leakage_on": {"vcc": 5.0},
    "input_leakage": {"vcc": 5.0},
}

POWER_TEST_DEFAULTS: dict[str, dict[str, Any]] = {
    "iq": {"vcc": 5.0},
    "vinmin": {"vcc": 5.0},
    "lir": {"vcc": 5.0},
    "lor": {"vcc": 5.0},
    "ioutmax": {"vcc": 5.0},
    "enable_current": {"vcc": 5.0},
}

# Per-family timing lookup (non-opamp must not inherit OPA settle/timeout)
FAMILY_TIMING: dict[str, dict[str, dict[str, float]]] = {
    "opamp": {
        "slew": {"timeout_s": _OPA_TIMEOUT_S, "settle_s": _OPA_SETTLE_SLEW_S},
        "_default": {"timeout_s": _OPA_TIMEOUT_S, "settle_s": _OPA_SETTLE_DEFAULT_S},
    },
    "logic": {
        "_default": {"timeout_s": 4.0, "settle_s": 0.3},
    },
    "switch": {
        "_default": {"timeout_s": 120.0, "settle_s": 0.5},
    },
    "lim": {
        "_default": {"timeout_s": 120.0, "settle_s": 0.5},
    },
    "power": {
        "_default": {"timeout_s": 120.0, "settle_s": 0.5},
    },
    "level": {
        "_default": {"timeout_s": 4.0, "settle_s": 0.3},
    },
    "demo_ingest": {
        "_default": {"timeout_s": 2.0, "settle_s": 0.1},
    },
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


def _load_part_yaml(part: str) -> dict[str, Any]:
    try:
        from ate.core.paths import PARTS_DIR
        import yaml as _yaml

        path = PARTS_DIR / f"{str(part or '').strip()}.yaml"
        if not path.is_file():
            return {}
        raw = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _num_list(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        return []
    out: list[float] = []
    for x in raw:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            continue
    return out


def controls_from_part(raw: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Operator dropdowns/numbers. Explicit yaml `controls:` wins, else VCC rails."""
    raw = raw if isinstance(raw, dict) else {}
    explicit = raw.get("controls")
    if isinstance(explicit, list) and explicit:
        out: list[dict[str, Any]] = []
        for row in explicit:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("id") or "").strip()
            if not cid:
                continue
            item: dict[str, Any] = {
                "id": cid,
                "label": str(row.get("label") or cid),
            }
            if row.get("value") is not None:
                item["value"] = row["value"]
            choices = row.get("choices") or row.get("options")
            nums = _num_list(choices)
            if nums:
                item["choices"] = nums
            elif isinstance(choices, list) and choices:
                item["choices"] = [str(x) for x in choices]
            out.append(item)
        if out:
            return out
    controls: list[dict[str, Any]] = []
    vcc = raw.get("vcc", raw.get("vcca"))
    sweeps = _num_list(
        raw.get("vcc_sweep_list")
        or raw.get("vcc_sweep")
        or raw.get("vcca_sweep_list")
        or raw.get("vcca_sweep")
    )
    if vcc is not None or sweeps:
        try:
            val = float(vcc) if vcc is not None else sweeps[0]
        except (TypeError, ValueError):
            val = sweeps[0] if sweeps else 5.0
        item = {
            "id": "vcc",
            "label": "VCCA (V)" if raw.get("vccb") is not None else "VCC (V)",
            "value": val,
        }
        if sweeps:
            item["choices"] = sweeps
        controls.append(item)
    if raw.get("vccb") is not None:
        item = {
            "id": "vccb",
            "label": "VCCB (V)",
            "value": float(raw["vccb"]),
        }
        sweeps_b = _num_list(raw.get("vccb_sweep_list") or raw.get("vccb_sweep"))
        if sweeps_b:
            item["choices"] = sweeps_b
        controls.append(item)
    return controls


def _apply_part_to_tests(tests: dict[str, Any], part_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Overlay part yaml vcc/vccb/test_defaults and filter enabled_tests."""
    from ate.fixture.modes import enabled_tests_for_part

    raw = _load_part_yaml(part_key)
    if not raw:
        return tests, {}
    vcc = raw.get("vcc", raw.get("vcca"))
    vccb = raw.get("vccb")
    if vcc is not None:
        vcc_f = float(vcc)
        for tid, entry in list(tests.items()):
            if isinstance(entry, dict) and "vcc" in entry:
                tests[tid] = {**entry, "vcc": vcc_f}
        vcc = vcc_f
    if vccb is not None:
        vccb_f = float(vccb)
        for tid, entry in list(tests.items()):
            if isinstance(entry, dict):
                tests[tid] = {**entry, "vccb": vccb_f}
        vccb = vccb_f
    else:
        for tid, entry in list(tests.items()):
            if isinstance(entry, dict) and "vccb" in entry:
                tests[tid] = {k: v for k, v in entry.items() if k != "vccb"}
    extra = raw.get("test_defaults")
    if isinstance(extra, dict):
        for tid, entry in extra.items():
            if not isinstance(entry, dict):
                continue
            tid_s = str(tid)
            tests[tid_s] = {**(tests.get(tid_s) or {}), **entry}
    enabled = enabled_tests_for_part(part_key)
    if enabled is not None:
        allow = set(enabled)
        tests = {k: v for k, v in tests.items() if k in allow}
        for tid in enabled:
            if tid in tests:
                continue
            stub: dict[str, Any] = {}
            if vcc is not None:
                stub["vcc"] = vcc
            if vccb is not None:
                stub["vccb"] = vccb
            tests[str(tid)] = stub
    return tests, raw


def timing_for(
    family: str | None = None,
    test_id: str | None = None,
    part: str | None = None,
) -> dict[str, float]:
    """Family-local settle/timeout; unknown non-opamp families get {} (no OPA fallback).

    Optional `part` overlays ate/config/parts/<part>.yaml `timing:` without copying OPA literals.
    """
    fam = (family or "opamp").strip().lower()
    if fam == "lim":
        fam = "switch"
    table = FAMILY_TIMING.get(fam)
    if table is None:
        out: dict[str, float] = {}
    else:
        key = (test_id or "").strip().lower()
        if key and key in table:
            out = dict(table[key])
        else:
            out = dict(table.get("_default") or {})
    if part:
        block = _load_part_yaml(part).get("timing")
        if isinstance(block, dict):
            if block.get("timeout_s") is not None:
                out["timeout_s"] = float(block["timeout_s"])
            if block.get("settle_s") is not None:
                out["settle_s"] = float(block["settle_s"])
    return out


def _opa_catalog(part: str) -> dict[str, Any]:
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
    raw = _load_part_yaml(part)
    sample = int(raw.get("sample_size") or 4) if raw else 4
    return {
        "tests": TEST_DEFAULTS,
        "psu_golden": _psu_golden_for_part(raw),
        "gain_profiles": profiles,
        "gbw_steps": GBW_FIXED_STEPS,
        "gbw_run_labels": GBW_RUN_LABELS,
        "controls": [],
        "sample_size": sample,
    }


def _empty_catalog() -> dict[str, Any]:
    return {
        "tests": {},
        "psu_golden": PSU_GOLDEN,
        "gain_profiles": {},
        "gbw_steps": [],
        "gbw_run_labels": {},
        "controls": [],
        "sample_size": 4,
    }


def _psu_golden_for_part(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(PSU_GOLDEN)
    raw = raw if isinstance(raw, dict) else {}
    ilim = raw.get("current_limit_a", raw.get("current_limit"))
    if ilim is not None:
        try:
            out["current_limit_a"] = float(ilim)
        except (TypeError, ValueError):
            pass
    return out


def _yaml_family_catalog(part_key: str, defaults: dict[str, Any]) -> dict[str, Any]:
    tests, raw = _apply_part_to_tests(dict(defaults), part_key)
    sample = int(raw.get("sample_size") or 4) if raw else 4
    cat = _empty_catalog()
    cat["tests"] = tests
    cat["controls"] = controls_from_part(raw)
    cat["sample_size"] = sample
    cat["psu_golden"] = _psu_golden_for_part(raw)
    return cat


def _logic_dc_for_catalog(part_key: str) -> dict[str, Any] | None:
    try:
        from ate.tests.logic.product_model import has_product_model, load_product_model, model_to_ui
    except Exception:
        return None
    if not has_product_model(part_key):
        return None
    overlay: dict[str, Any] = {}
    try:
        from ate.core.database import get_context

        overlay = get_context().load_test_params() or {}
    except Exception:
        overlay = {}
    model = load_product_model(part_key, overlay=overlay or None)
    if model is None:
        return None
    ui = model_to_ui(model)
    from ate.core.specs import load_part_specs

    ui["specs"] = load_part_specs(part_key, overlay=overlay)
    try:
        from ate.fixture.modes import enabled_tests_for_part

        ui["enabled_tests"] = list(enabled_tests_for_part(part_key) or [])
    except Exception:
        ui["enabled_tests"] = []
    if overlay.get("sample_size") is not None:
        try:
            ui["sample_size"] = max(1, int(overlay["sample_size"]))
        except (TypeError, ValueError):
            pass
    elif model.sample_size:
        ui["sample_size"] = int(model.sample_size)
    return ui


def catalog_for_ui(part: str = "rs622", family: str | None = None) -> dict[str, Any]:
    fam = (family or "opamp").strip().lower()
    if fam == "lim":
        fam = "switch"
    if fam == "opamp":
        return _opa_catalog(part)
    if fam == "logic":
        cat = _yaml_family_catalog(str(part or "rs29511"), LOGIC_TEST_DEFAULTS)
        logic_dc = _logic_dc_for_catalog(str(part or ""))
        if logic_dc:
            cat["logic_dc"] = logic_dc
            if logic_dc.get("sample_size"):
                try:
                    cat["sample_size"] = max(1, int(logic_dc["sample_size"]))
                except (TypeError, ValueError):
                    pass
        return cat
    if fam == "switch":
        return _yaml_family_catalog(str(part or "rs2323"), LIM_TEST_DEFAULTS)
    if fam == "power":
        return _yaml_family_catalog(str(part or "rs3213"), POWER_TEST_DEFAULTS)
    # extra families: no OPA TEST_DEFAULTS. Part yaml controls only if this part belongs here.
    raw = _load_part_yaml(str(part or ""))
    cat = _empty_catalog()
    if raw:
        comp = str(raw.get("component") or "").lower().replace(" ", "").replace("_", "")
        fam_n = fam.replace(" ", "").replace("_", "")
        if comp and (
            comp == fam_n
            or (fam_n == "switch" and comp in ("analogswitch", "switch", "lim"))
            or (fam_n == "power" and comp in ("power", "ldo"))
        ):
            cat["controls"] = controls_from_part(raw)
            cat["sample_size"] = int(raw.get("sample_size") or 4)
    return cat
