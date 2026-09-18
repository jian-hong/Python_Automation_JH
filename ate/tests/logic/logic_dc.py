"""Shared Path B Logic DC runner.

One code path for 2-input AND (RS1G08) and 3-input RS1G97. Differences live
in product_model YAML (truth table, isolation, pin roles, limits, recipe).
OE optional: IOZ only when oe != none.

Does not import Ariff.* / Lim.* / See Lim goldens. Dual-rail RS0204 keeps
its own bodies; voh/vol/icc dispatch there only when the part has vcca/vccb
and no Path B model.

INSTRUMENT_SENSE ICC: DMM-on-VCC (DMM in series with PSU CH1 / DUT VCC).
INSTRUMENT_SENSE DELTA_ICC: DMM-on-VCC; one input at recipe.delta_offset_v
  below VCC, or at dc_limits.ICCT_uA.one_input_V when ICCT is mapped (not 0.6).
INSTRUMENT_SENSE II: DMM in series with the swept input pin (force VI via AWG/PSU).
INSTRUMENT_SENSE VOH: force Y-high from truth_table vector; DMM sense V(Y).
  Loaded IOH from CONFIRMED voh_table (PSU CH2 Y-load sink rail 0V unless vref given).
INSTRUMENT_SENSE VOL: force Y-low from truth_table vector; DMM sense V(Y).
  Loaded IOL from CONFIRMED vol_table (PSU CH2 Y-load source rail = VCC unless vref given).
SETTLE: measure-after-settle (recipe settle_s / stable_n / stable_eps_V / settle_timeout_s).
  Voltage uses stable_eps_V. Current (ICC / ΔICC / II / IOZ) uses stable_eps_A only
  (never reuse stable_eps_V as amps). If stable_eps_A is set (panel/overlay),
  eps/N + hard timeout (RuntimeError / FAIL; never last-reading). If
  stable_eps_A is null: tight-settle claims stay FAIL-closed; honest path waits
  settle_s once then measures and tags settle=NON_TIGHT (not greenable as
  tight-settle). Do not invent a uA default.
INSTRUMENT_SENSE IOZ: OE inactive; DMM in series with Y; PSU CH2 force Vout.
  Not applicable when oe=none. Open-drain Y=Z is not IOZ.
  Open-drain: skip VOH (not a push-pull high). Sequential shift register is
  not combinational 2^n ICC.

truth_table.status UNCONFIRMED is not Datasheet-signed and is not greenable.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from ate.core.registry import TestSpec, register
from ate.tests.logic.product_model import (
    DriveMap,
    IsolationPattern,
    ProductModel,
    has_product_model,
    icc_pins,
    isolation_for_run,
    iter_logic_corners,
    ioz_force_vector,
    is_datasheet_signed,
    is_open_drain,
    is_sequential,
    is_unconfirmed_status,
    voh_series_allowed,
    load_part_yaml,
    load_product_model,
    logic_volts,
    lookup_pass_mode,
    lookup_vcc_grid_limits,
    operator_pause,
    path_b_handoff,
    resolve_data_paths,
    vcc_grid_stimulus,
    vcc_grid_unconfirmed,
    vectors_for_output,
)

_NOTE = "Path B Logic DC -- product_model YAML; not a per-chip fork"

_LOGIC_FIXTURE = "LOGIC"


def _require(instr, *names: str) -> None:
    remap = {"MSO": "scope", "PSU": "psu", "AWG": "gen", "DMM": "dmm"}
    missing = [n for n in names if getattr(instr, remap[n], None) is None]
    if missing:
        raise RuntimeError(f"Missing instruments: {', '.join(missing)}")


def _needs_awg(model: ProductModel) -> bool:
    if any(dm.src == "awg" for dm in (model.pin_drive or {}).values()):
        return True
    return vcc_grid_stimulus(model) == "AWG"


def _needs_mso(model: ProductModel, test_id: str) -> bool:
    tid = str(test_id or "").strip().lower()
    if vcc_grid_stimulus(model) != "PSU_MSO":
        return False
    return tid in {"input_threshold", "vth"}


def _require_for(instr, model: ProductModel, test_id: str = "") -> None:
    names = ["PSU", "DMM"]
    if _needs_awg(model):
        names.append("AWG")
    if _needs_mso(model, test_id):
        names.append("MSO")
    _require(instr, *names)


def _pause(params: Any, title: str, checklist: Optional[list[str]] = None) -> bool:
    return operator_pause(params, title, checklist)


def _campaign_overlay() -> dict[str, Any]:
    """Version overlay from _manifest/test_params.yaml. Empty if no campaign."""
    try:
        from ate.core.database import get_context

        blob = get_context().load_test_params()
        return blob if isinstance(blob, dict) else {}
    except Exception:
        return {}


def _model(params: Any) -> ProductModel:
    key = str(getattr(params, "part", None) or "").strip().lower()
    overlay = getattr(params, "test_params", None)
    if not isinstance(overlay, dict):
        overlay = _campaign_overlay()
    model = load_product_model(key, overlay=overlay or None)
    if model is None:
        raise RuntimeError(
            f"Path B Logic DC: part {key!r} has no product_model "
            "(logic_inputs / pins / truth_table). Add YAML; do not fork Python."
        )
    return model


def _current_limit(params: Any, model: ProductModel) -> float:
    cfg = load_part_yaml(str(getattr(params, "part", "") or "").lower())
    return float(
        getattr(params, "current_limit_a", None)
        or getattr(params, "current_limit", None)
        or cfg.get("current_limit")
        or model.recipe.get("current_limit")
        or 0.05
    )


def _uses_truth_table(test_id: str) -> bool:
    return str(test_id or "").strip().lower() in {
        "input_threshold",
        "vth",
        "voh",
        "vol",
    }


def _provisional_dc(model: ProductModel, test_id: str) -> bool:
    dc = model.dc_limits if isinstance(model.dc_limits, dict) else {}
    tid = str(test_id or "").strip()
    low = tid.lower()
    if low == "voh":
        keys: tuple[str, ...] = ("VOH", "voh")
    elif low == "vol":
        keys = ("VOL", "vol")
    else:
        keys = (tid, low, tid.upper())
    for key in keys:
        block = dc.get(key)
        if not isinstance(block, dict):
            continue
        st = str(block.get("status") or "").strip().upper().replace("-", "_")
        if st in ("N_A", "NA", "ABSENT"):
            return False
        if is_unconfirmed_status(block.get("status")):
            return True
        return False
    return False


def _meas(
    model: ProductModel,
    meas_id: str,
    value: Any,
    unit: str,
    *,
    test_id: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {"id": meas_id, "value": value, "unit": unit}
    mode = lookup_pass_mode(model, meas_id, test_id)
    if mode:
        row["pass_mode"] = mode
    if _uses_truth_table(test_id) and is_unconfirmed_status(model.truth_table_status):
        row["greenable"] = False
        row["status"] = model.truth_table_status or "UNCONFIRMED"
    if _provisional_dc(model, test_id):
        row["greenable"] = False
        row["status"] = "PROVISIONAL"
    if str(test_id or "").strip().lower() in {"input_threshold", "vth"} and vcc_grid_unconfirmed(model):
        row["greenable"] = False
        row["status"] = "UNCONFIRMED"
    return row


_CURRENT_SETTLE_IDS = frozenset({"icc", "delta_icc", "ii", "ioz"})


def _current_settle_tag(model: ProductModel) -> str:
    """TIGHT when stable_eps_A is a positive amp number; else NON_TIGHT."""
    if _recipe_optional_positive(model, "stable_eps_A") is None:
        return "NON_TIGHT"
    return "TIGHT"


def _finish(model: ProductModel, test_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach schema status. UNCONFIRMED / PROVISIONAL cannot report green."""
    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}
        payload["data"] = data
    data["truth_table_status"] = model.truth_table_status
    data["isolation_status"] = model.isolation_status
    data["pass_mode"] = dict(model.pass_mode)
    data["vcc_list"] = list(model.vcc_list)
    signed = is_datasheet_signed(model.truth_table_status)
    uses_tt = _uses_truth_table(test_id)
    greenable = signed and not _provisional_dc(model, test_id)
    if uses_tt and is_unconfirmed_status(model.truth_table_status):
        greenable = False
    if str(test_id or "").strip().lower() in {"input_threshold", "vth"} and vcc_grid_unconfirmed(model):
        greenable = False
    data["greenable"] = bool(greenable)
    data["vcc_grid"] = dict(model.vcc_grid or {})
    data["stimulus"] = vcc_grid_stimulus(model)
    if not greenable and uses_tt:
        tag = (
            f"truth_table.status={model.truth_table_status or 'UNCONFIRMED'} "
            "(not Datasheet-signed; not greenable)"
        )
        summary = str(payload.get("summary") or "").strip()
        payload["summary"] = f"{summary} [{tag}]".strip()
        for row in data.get("rows") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("Result") or "").upper() == "PASS":
                row["Result"] = "UNCONFIRMED"
            row.setdefault("status", model.truth_table_status or "UNCONFIRMED")
    tid = str(test_id or "").strip().lower()
    paths = resolve_data_paths(model, tid)
    if paths:
        data["data_paths"] = paths
    if tid in _CURRENT_SETTLE_IDS:
        settle = _current_settle_tag(model)
        data["settle"] = settle
        tight_ok = settle == "TIGHT"
        data["tight_settle_greenable"] = tight_ok
        if settle == "NON_TIGHT":
            summary = str(payload.get("summary") or "").strip()
            payload["summary"] = (
                f"{summary} [settle=NON_TIGHT; not greenable as tight-settle]"
            ).strip()
        for row in data.get("rows") or []:
            if isinstance(row, dict):
                row.setdefault("settle", settle)
        for meas in payload.get("measurements") or []:
            if isinstance(meas, dict):
                meas["settle"] = settle
                meas["tight_settle_greenable"] = tight_ok
    return payload


def _vcc_now(params: Any, model: ProductModel) -> float:
    try:
        if getattr(params, "vcc", None) is not None:
            return float(params.vcc)
    except (TypeError, ValueError):
        pass
    if model.vcc_list:
        return float(model.vcc_list[0])
    return 5.0


def _vcc_corners(params: Any, model: ProductModel, recipe_key: str = "") -> list[float]:
    """vcc_list / recipe lists only. vcc_op_min/max are range metadata, not a sweep."""
    extra = model.recipe.get(recipe_key) if recipe_key else None
    if isinstance(extra, list) and extra:
        return [float(x) for x in extra]
    if model.vcc_list:
        return list(model.vcc_list)
    return [_vcc_now(params, model)]


def _step_v(model: ProductModel) -> float:
    raw = model.recipe.get("threshold_step_v")
    try:
        v = float(raw)
        if v > 0:
            return v
    except (TypeError, ValueError):
        pass
    return 0.05


def _recipe_num(model: ProductModel, key: str, default: float) -> float:
    raw = model.recipe.get(key)
    try:
        if raw is not None:
            return float(raw)
    except (TypeError, ValueError):
        pass
    return float(default)


def _recipe_optional_positive(model: ProductModel, key: str) -> float | None:
    """Recipe number or None. Empty / null / non-numeric -> None (not a default)."""
    raw = model.recipe.get(key)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip().lower() in ("", "null", "none", "~", "nan"):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return v


def _wait_settled(
    dmm,
    model: ProductModel,
    *,
    kind: str = "voltage",
    setup: bool = True,
    tight: bool = False,
) -> float:
    """Wait settle_s, then measure until stable_n within eps, or FAIL.

    Measure-after-settle, not before. Recipe is not a DC limit.
    kind voltage: DMM volts vs stable_eps_V.
    kind current: DMM amps vs stable_eps_A only (never reuse stable_eps_V).
    If stable_eps_A is null: tight=True raises FAIL-closed. tight=False waits
    settle_s once then one reading (settle=NON_TIGHT; not greenable as
    tight-settle). Do not invent a uA default.
    When stable_eps_A is set: eps/N + hard timeout. Timeout raises RuntimeError
    (FAIL). Never returns the last reading. Sleep is capped by remaining time
    so this cannot hang forever.
    """
    from dmm_setup import dmm_read, dmm_setup_current, dmm_setup_voltage

    if kind not in ("voltage", "current"):
        raise RuntimeError(f"settle kind {kind!r} must be voltage or current")
    settle_s = max(0.0, _recipe_num(model, "settle_s", 0.05))
    try:
        n = int(model.recipe.get("stable_n") or 3)
    except (TypeError, ValueError):
        n = 3
    n = max(1, n)
    if kind == "current":
        eps_a = _recipe_optional_positive(model, "stable_eps_A")
        if eps_a is None:
            if tight:
                raise RuntimeError(
                    "stable_eps_A missing: tight current settle FAIL-closed "
                    "(do not reuse stable_eps_V / 0.005 V as amps). "
                    "Set recipe.stable_eps_A or campaign test_params overlay. "
                    "Do not invent a uA default. Honest path (tight=False): "
                    "wait settle_s once then measure; tag settle=NON_TIGHT."
                )
            if setup:
                dmm_setup_current(dmm)
            if settle_s > 0:
                time.sleep(settle_s)
            return float(dmm_read(dmm))
        if eps_a <= 0:
            raise RuntimeError("stable_eps_A must be > 0 A (amps; not volts)")
        eps = eps_a
    else:
        eps = _recipe_num(model, "stable_eps_V", 0.005)
    timeout = _recipe_num(model, "settle_timeout_s", 2.0)
    if timeout <= 0:
        raise RuntimeError(f"settle timeout {timeout}s: invalid (must be > 0; never hang)")
    if setup:
        if kind == "current":
            dmm_setup_current(dmm)
        else:
            dmm_setup_voltage(dmm)
    t0 = time.monotonic()
    window: list[float] = []
    max_iters = n + 8 + int(timeout / max(settle_s, 0.001) + 1)
    for _ in range(max_iters):
        remaining = timeout - (time.monotonic() - t0)
        if remaining <= 0:
            raise RuntimeError(
                f"settle timeout {timeout}s: DMM {kind} not stable "
                f"(need {n} within {eps}, got {window!r})"
            )
        time.sleep(min(settle_s, remaining) if settle_s > 0 else 0.0)
        if (time.monotonic() - t0) >= timeout:
            raise RuntimeError(
                f"settle timeout {timeout}s: DMM {kind} not stable "
                f"(need {n} within {eps}, got {window!r})"
            )
        v = float(dmm_read(dmm))
        window.append(v)
        if len(window) > n:
            window = window[-n:]
        if len(window) >= n and (max(window) - min(window)) <= eps:
            return sum(window) / len(window)
    raise RuntimeError(
        f"settle timeout {timeout}s: DMM {kind} not stable "
        f"(need {n} within {eps}, got {window!r})"
    )


def _wait_settled_voltage(dmm, model: ProductModel, *, setup: bool = True) -> float:
    """Settled DMM voltage. Timeout raises RuntimeError / FAIL."""
    return _wait_settled(dmm, model, kind="voltage", setup=setup)


def _wait_settled_current_ua(
    dmm, model: ProductModel, *, setup: bool = True, tight: bool = False
) -> float:
    """DMM current in uA. tight=True FAIL-closes when stable_eps_A is null.

    Default tight=False: null eps waits settle_s once (NON_TIGHT). When
    stable_eps_A is set, eps/N hard-FAIL timeout. Never reuses stable_eps_V.
    """
    return _wait_settled(dmm, model, kind="current", setup=setup, tight=tight) * 1e6


def _vmax_for_ii(model: ProductModel, vcc: float) -> float:
    """VI force for II. Uses vcc_op_max as pin voltage metadata, not a VCC corner."""
    if model.vcc_op_max is not None:
        return float(model.vcc_op_max)
    if model.vcc_list:
        return max(model.vcc_list)
    return float(vcc)


def _is_dual_rail(part_key: str) -> bool:
    cfg = load_part_yaml(part_key)
    return cfg.get("vccb") is not None or (
        cfg.get("vcca") is not None and not has_product_model(part_key)
    )


def _legacy_dual_rail(test_id: str, instr, params: Any) -> dict[str, Any]:
    from ate.tests.logic import rs0204

    fn = rs0204._RUN.get(test_id)
    if fn is None:
        raise RuntimeError(f"{test_id}: no dual-rail body")
    return fn(instr, params)


def _dispatch_shared(test_id: str, path_b, instr, params: Any) -> dict[str, Any]:
    key = str(getattr(params, "part", "") or "").strip().lower()
    if has_product_model(key):
        return path_b(instr, params)
    if _is_dual_rail(key):
        return _legacy_dual_rail(test_id, instr, params)
    raise RuntimeError(
        f"{test_id}: part {key!r} has no Path B product_model and is not dual-rail. "
        "Add product_model YAML (do not copy RS0204 dual-rail)."
    )


def _power_vcc(instr, vcc: float, ilim: float) -> None:
    from psu_setup import power_on_protected

    power_on_protected(instr.psu, 1, vcc, ilim, ovp=max(5.6, vcc * 1.1))
    # Caller must settle-to-stable (voltage or current) after this VCC switch.


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


def _setup_dc(gen, ch: int, volts: float) -> bool:
    from generator_setup import setup_dc

    return bool(setup_dc(gen, ch, float(volts)))


def _force_psu(instr, ch: int, volts: float, ilim: float) -> None:
    from psu_setup import power_on_protected

    power_on_protected(instr.psu, ch, float(volts), ilim, ovp=max(5.6, abs(float(volts)) * 1.1 + 0.5))


def _drive_for_sweep(model: ProductModel, sweep_pin: str) -> dict[str, DriveMap]:
    """PSU_MSO keeps YAML pin_drive. AWG stimulus: swept pin on AWG CH1."""
    drives = dict(model.pin_drive)
    sweep = str(sweep_pin).upper()
    if vcc_grid_stimulus(model) == "PSU_MSO":
        if sweep not in drives:
            raise RuntimeError(
                f"PSU_MSO: pin_drive missing {sweep} (keep YAML map; do not steal AWG CH1)"
            )
        return drives
    drives[sweep] = DriveMap(src="awg", ch=1)
    for name, dm in list(drives.items()):
        if name == sweep:
            continue
        if dm.src == "awg" and dm.ch == 1:
            drives[name] = DriveMap(src="awg", ch=2)
    return drives


def _apply_pin(instr, drive: DriveMap, volts: float, ilim: float) -> None:
    if drive.src == "awg":
        if getattr(instr, "gen", None) is None:
            raise RuntimeError("Missing instruments: AWG")
        if not _setup_dc(instr.gen, drive.ch, volts):
            raise RuntimeError(f"AWG CH{drive.ch} DC setup failed at {volts} V")
        return
    if drive.src == "psu":
        if drive.ch == 1:
            raise RuntimeError("PSU CH1 is VCC; pin_drive must not steal it")
        _force_psu(instr, drive.ch, volts, ilim)
        return
    raise RuntimeError(f"Unknown pin_drive src {drive.src!r}")


def _apply_levels(
    instr,
    model: ProductModel,
    levels: dict[str, Any],
    vcc: float,
    ilim: float,
    *,
    drives: dict[str, DriveMap] | None = None,
) -> None:
    dmap = drives or model.pin_drive
    for pin, lv in levels.items():
        drive = dmap.get(str(pin).upper())
        if drive is None:
            raise RuntimeError(
                f"No pin_drive for {pin!r}. Add pin_drive in product_model YAML."
            )
        _apply_pin(instr, drive, logic_volts(lv, vcc), ilim)


def _avg_voltage(dmm, n: int = 3) -> float:
    from dmm_setup import dmm_read, dmm_setup_voltage

    dmm_setup_voltage(dmm)
    readings = [float(dmm_read(dmm)) for _ in range(max(1, n))]
    return sum(readings) / len(readings)


def _mid(vcc: float) -> float:
    return float(vcc) / 2.0


def _transition(
    prev: Optional[float],
    vout: float,
    mid: float,
    y_expect: str,
    vin_rising: bool,
) -> bool:
    if prev is None:
        return False
    track = y_expect != "invert"
    went_high = prev < mid <= vout
    went_low = prev >= mid > vout
    if track:
        return went_high if vin_rising else went_low
    return went_low if vin_rising else went_high


def _sweep_threshold(
    instr,
    *,
    model: ProductModel,
    vcc: float,
    ilim: float,
    pattern: IsolationPattern,
    rising: bool,
) -> Optional[float]:
    drives = _drive_for_sweep(model, pattern.sweep_pin)
    _apply_levels(instr, model, pattern.fix, vcc, ilim, drives=drives)
    _wait_settled_voltage(instr.dmm, model)
    search = (model.recipe or {}).get("search")
    sweep_drive = drives[pattern.sweep_pin]
    if isinstance(search, dict) and search:
        from ate.tests.logic.threshold_search import run_search_stage

        lim = lookup_vcc_grid_limits(model, vcc) or {}
        limit = lim.get("VIH_min_V") if rising else lim.get("VIL_max_V")
        try:
            limit_f = float(limit) if limit is not None else None
        except (TypeError, ValueError):
            limit_f = None

        def _measure(vin: float) -> float:
            _apply_pin(instr, sweep_drive, float(vin), ilim)
            return float(_wait_settled_voltage(instr.dmm, model, setup=False))

        result = run_search_stage(
            _measure,
            vcc=float(vcc),
            rising=rising,
            limit=limit_f,
            search=search,
            y_expect=pattern.y_expect,
            mid=_mid(vcc),
        )
        return result.vin
    step = _step_v(model)
    n = int(round(vcc / step))
    seq = list(range(0, n + 1))
    if not rising:
        seq = list(reversed(seq))
    found: Optional[float] = None
    prev: Optional[float] = None
    for i in seq:
        vin = min(vcc, i * step)
        _apply_pin(instr, sweep_drive, vin, ilim)
        vout = _wait_settled_voltage(instr.dmm, model, setup=False)
        if _transition(prev, vout, _mid(vcc), pattern.y_expect, rising):
            found = vin
            break
        prev = vout
    return found


def _run_input_threshold(instr, params: Any) -> dict[str, Any]:
    model = _model(params)
    _require_for(instr, model, "input_threshold")
    with path_b_handoff(params, model, "input_threshold"):
        ilim = _current_limit(params, model)
        vccs = _vcc_corners(params, model)
        schmitt = bool(model.schmitt)
        rows: list[dict[str, Any]] = []
        try:
            for vcc in vccs:
                _power_vcc(instr, vcc, ilim)
                for pin in model.logic_inputs:
                    pats = isolation_for_run(model, pin)
                    if not pats:
                        rows.append(
                            {
                                "VCC": vcc,
                                "PIN": pin,
                                "status": "UNSURE",
                                "note": "no isolation pattern (unused ties not in YAML / not derivable)",
                            }
                        )
                        continue
                    for pat in pats:
                        rising_first = pattern_rising_first(pat)
                        rise = _sweep_threshold(
                            instr, model=model, vcc=vcc, ilim=ilim, pattern=pat, rising=True
                        )
                        fall = _sweep_threshold(
                            instr, model=model, vcc=vcc, ilim=ilim, pattern=pat, rising=False
                        )
                        if not rising_first:
                            # invert / VIL reverse: still record both; VIL is falling-vin
                            pass
                        hyst = None
                        if rise is not None and fall is not None:
                            hyst = round(float(rise) - float(fall), 4)
                        rec: dict[str, Any] = {
                            "VCC": vcc,
                            "PIN": pin,
                            "fix": dict(pat.fix),
                            "y_expect": pat.y_expect,
                        }
                        lim = lookup_vcc_grid_limits(model, vcc) or {}
                        if lim:
                            rec["vcc_owner"] = lim.get("source")
                            rec["VIH_min_V"] = lim.get("VIH_min_V")
                            rec["VIL_max_V"] = lim.get("VIL_max_V")
                        if schmitt:
                            rec["VT+"] = rise
                            rec["VT-"] = fall
                            rec["HYSTERESIS_V"] = hyst
                        else:
                            rec["VIH"] = rise
                            rec["VIL"] = fall
                            rec["HYSTERESIS_V"] = hyst
                        rows.append(rec)
        finally:
            _power_down(instr)
        if not rows:
            raise RuntimeError("input_threshold: no isolation rows measured")
        last = rows[-1]
        if schmitt:
            summary = f"VTH n={len(rows)} last VT+={last.get('VT+')} VT-={last.get('VT-')}"
            meas = []
            vt_p = [r.get("VT+") for r in rows if r.get("VT+") is not None]
            vt_m = [r.get("VT-") for r in rows if r.get("VT-") is not None]
            if vt_p:
                meas.append(_meas(model, "VTPLUS_V", vt_p[-1], "V", test_id="input_threshold"))
            if vt_m:
                meas.append(_meas(model, "VTMINUS_V", vt_m[-1], "V", test_id="input_threshold"))
        else:
            summary = f"VTH n={len(rows)} last VIH={last.get('VIH')} VIL={last.get('VIL')}"
            meas = []
            for rec in rows:
                vcc = rec.get("VCC")
                tag = str(vcc).replace(".", "p")
                lim = lookup_vcc_grid_limits(model, vcc) or {}
                if rec.get("VIH") is not None:
                    row = _meas(model, f"VIH_{tag}V", rec["VIH"], "V", test_id="input_threshold")
                    if lim.get("VIH_min_V") is not None:
                        row["min"] = lim["VIH_min_V"]
                    row["pass_mode"] = lookup_pass_mode(model, "VIH", "input_threshold") or "min_only"
                    meas.append(row)
                if rec.get("VIL") is not None:
                    row = _meas(model, f"VIL_{tag}V", rec["VIL"], "V", test_id="input_threshold")
                    if lim.get("VIL_max_V") is not None:
                        row["max"] = lim["VIL_max_V"]
                    row["pass_mode"] = lookup_pass_mode(model, "VIL", "input_threshold") or "max_only"
                    meas.append(row)
            if last.get("VIH") is not None:
                last_vih = _meas(model, "VIH_V", last["VIH"], "V", test_id="input_threshold")
                lim_last = lookup_vcc_grid_limits(model, last.get("VCC")) or {}
                if lim_last.get("VIH_min_V") is not None:
                    last_vih["min"] = lim_last["VIH_min_V"]
                meas.append(last_vih)
            if last.get("VIL") is not None:
                last_vil = _meas(model, "VIL_V", last["VIL"], "V", test_id="input_threshold")
                lim_last = lookup_vcc_grid_limits(model, last.get("VCC")) or {}
                if lim_last.get("VIL_max_V") is not None:
                    last_vil["max"] = lim_last["VIL_max_V"]
                meas.append(last_vil)
        return _finish(
            model,
            "input_threshold",
            {"summary": summary, "data": {"rows": rows, "schmitt": schmitt}, "measurements": meas},
        )


def pattern_rising_first(pat: IsolationPattern) -> bool:
    return str(pat.vil_sweep or "").lower() not in ("reverse", "falling", "vil_reverse")


def _run_icc(instr, params: Any) -> dict[str, Any]:
    # INSTRUMENT_SENSE ICC: DMM-on-VCC (series with PSU CH1 / DUT VCC).
    model = _model(params)
    if is_sequential(model):
        raise RuntimeError(
            "icc: sequential_shift_register is not combinational 2^n. "
            "Do not run Path B gate ICC."
        )
    _require_for(instr, model, "icc")
    with path_b_handoff(params, model, "icc"):
        ilim = _current_limit(params, model)
        pins = icc_pins(model)
        corners = iter_logic_corners(pins)
        vccs = _vcc_corners(params, model)
        rows: list[dict[str, Any]] = []
        try:
            for vcc in vccs:
                _power_vcc(instr, vcc, ilim)
                _wait_settled_current_ua(instr.dmm, model)
                any_ok = False
                for vec in corners:
                    _apply_levels(instr, model, vec, vcc, ilim)
                    i_ua = _wait_settled_current_ua(instr.dmm, model, setup=False)
                    rec = {"VCC": vcc, "ICC_uA": i_ua}
                    rec.update({f"IN_{k}": v for k, v in vec.items()})
                    rows.append(rec)
                    any_ok = True
                if not any_ok:
                    raise RuntimeError(f"icc: no corners at VCC={vcc}")
        finally:
            _power_down(instr)
        mx = max((abs(float(r["ICC_uA"])) for r in rows), default=0.0)
        return _finish(
            model,
            "icc",
            {
                "summary": f"ICC n={len(rows)} max={mx:.3f} uA ({len(pins)} pins, 2^{len(pins)} corners)",
                "data": {"rows": rows, "instrument_sense": "DMM-on-VCC"},
                "measurements": [_meas(model, "ICC_uA", mx, "uA", test_id="icc")],
            },
        )


def _icct_blob(model: ProductModel) -> dict[str, Any]:
    """ICCT maps to delta_icc via one_input_V or card offset_v. Do not invent 0.6."""
    dc = model.dc_limits if isinstance(model.dc_limits, dict) else {}
    for key in ("ICCT_uA", "ICCT", "icct"):
        block = dc.get(key)
        if not isinstance(block, dict):
            continue
        st = str(block.get("status") or "").strip().upper().replace("-", "_")
        if st in ("ABSENT", "N_A", "NA"):
            continue
        if (
            block.get("one_input_V") is not None
            or block.get("offset_v") is not None
            or str(block.get("map_to") or "").strip().lower() == "delta_icc"
        ):
            return block
    return {}


def _delta_force_v(model: ProductModel, vcc: float) -> float:
    icct = _icct_blob(model)
    one = icct.get("one_input_V")
    if one is not None:
        return float(one)
    offset = icct.get("offset_v")
    if offset is None:
        offset = model.recipe.get("delta_offset_v")
    if offset is None:
        raise RuntimeError(
            "delta_icc: need dc_limits.ICCT_uA.one_input_V / offset_v or "
            "recipe.delta_offset_v (do not invent 0.6)"
        )
    return max(0.0, float(vcc) - float(offset))


def _delta_vccs(params: Any, model: ProductModel) -> list[float]:
    icct = _icct_blob(model)
    if icct.get("vcc") is not None:
        return [float(icct["vcc"])]
    vccs = _vcc_corners(params, model, "delta_vcc_list")
    vmin = icct.get("vcc_min")
    if vmin is None:
        vmin = model.recipe.get("delta_vcc_min")
    if vmin is not None:
        vccs = [v for v in vccs if v + 1e-9 >= float(vmin)]
        if not vccs:
            raise RuntimeError(
                "delta_icc: no vcc_list points at/above ICCT vcc_min / recipe.delta_vcc_min"
            )
    return vccs


def _run_delta_icc(instr, params: Any) -> dict[str, Any]:
    # INSTRUMENT_SENSE DELTA_ICC: DMM-on-VCC; one input at offset or ICCT voltage.
    model = _model(params)
    if is_sequential(model):
        raise RuntimeError(
            "delta_icc: sequential_shift_register is not combinational 2^n. "
            "ICCT absent -- do not run Path B gate delta_icc."
        )
    near_note = ""
    icct = _icct_blob(model)
    if icct.get("one_input_V") is not None:
        near_note = f"ICCT one_in={icct.get('one_input_V')}V @{icct.get('vcc')}"
    elif icct.get("offset_v") is not None or model.recipe.get("delta_offset_v") is not None:
        off = icct.get("offset_v")
        if off is None:
            off = model.recipe.get("delta_offset_v")
        near_note = f"VCC-{off}"
    else:
        raise RuntimeError(
            "delta_icc: recipe.delta_offset_v missing (datasheet dICC, e.g. VCC-0.6). "
            "Do not invent; add ICCT one_input_V or offset to product_model YAML."
        )
    _require_for(instr, model, "delta_icc")
    with path_b_handoff(params, model, "delta_icc"):
        ilim = _current_limit(params, model)
        vccs = _delta_vccs(params, model)
        pins = list(model.logic_inputs)
        if model.has_oe() and model.oe_pin:
            if model.oe_pin not in pins:
                pins.append(model.oe_pin)
        rows: list[dict[str, Any]] = []
        try:
            for vcc in vccs:
                _power_vcc(instr, vcc, ilim)
                _wait_settled_current_ua(instr.dmm, model)
                near_v = _delta_force_v(model, vcc)
                for near in pins:
                    for others_high in (True, False):
                        levels: dict[str, Any] = {}
                        for p in pins:
                            if p == near:
                                continue
                            levels[p] = "H" if others_high else "L"
                        if model.has_oe() and model.oe_pin not in levels:
                            levels[model.oe_pin] = model.oe_active_level()
                        _apply_levels(instr, model, levels, vcc, ilim)
                        _wait_settled_current_ua(instr.dmm, model, setup=False)
                        drive = model.pin_drive.get(near)
                        if drive is None:
                            raise RuntimeError(f"delta_icc: no pin_drive for {near}")
                        _apply_pin(instr, drive, near_v, ilim)
                        i_ua = _wait_settled_current_ua(instr.dmm, model, setup=False)
                        rows.append(
                            {
                                "VCC": vcc,
                                "NEAR_PIN": near,
                                "NEAR_V": near_v,
                                "OTHERS": "H" if others_high else "L",
                                "ICC_uA": i_ua,
                            }
                        )
        finally:
            _power_down(instr)
        if not rows:
            raise RuntimeError("delta_icc: no points")
        mx = max(abs(float(r["ICC_uA"])) for r in rows)
        return _finish(
            model,
            "delta_icc",
            {
                "summary": f"DeltaICC n={len(rows)} max={mx:.3f} uA {near_note}".strip(),
                "data": {"rows": rows, "instrument_sense": "DMM-on-VCC"},
                "measurements": [_meas(model, "DELTA_ICC_uA", mx, "uA", test_id="delta_icc")],
            },
        )


def _run_ii(instr, params: Any) -> dict[str, Any]:
    # INSTRUMENT_SENSE II: DMM in series with the swept input; force VI.
    model = _model(params)
    _require_for(instr, model, "ii")
    with path_b_handoff(params, model, "ii"):
        ilim = _current_limit(params, model)
        vccs = _vcc_corners(params, model, "ii_vcc_list")
        rows: list[dict[str, Any]] = []
        try:
            for pin in model.logic_inputs:
                vmax = None
                for vcc in vccs:
                    vmax = _vmax_for_ii(model, vcc)
                    if not _pause(
                        params,
                        f"II: DMM in series with input {pin} (VI=0 and VI={vmax} V). "
                        "Other inputs at rail. Continue.",
                        [
                            f"DMM series input {pin} (CONFIRMED pin; do not invent nets)",
                            f"VI=0 and VI={vmax} V",
                            "Other inputs at rail",
                            "Then Continue",
                        ],
                    ):
                        raise RuntimeError(f"ii: operator stopped before pin {pin}")
                    _power_vcc(instr, vcc, ilim)
                    _wait_settled_current_ua(instr.dmm, model)
                    others = {p: "H" for p in model.logic_inputs if p != pin}
                    if model.has_oe():
                        others[model.oe_pin] = model.oe_active_level()
                    _apply_levels(instr, model, others, vcc, ilim)
                    _wait_settled_current_ua(instr.dmm, model, setup=False)
                    drive = model.pin_drive.get(pin)
                    if drive is None:
                        raise RuntimeError(f"ii: no pin_drive for {pin}")
                    for vi in (0.0, float(vmax)):
                        _apply_pin(instr, drive, vi, ilim)
                        i_ua = _wait_settled_current_ua(instr.dmm, model, setup=False)
                        rows.append({"VCC": vcc, "PIN": pin, "VI": vi, "II_uA": i_ua})
        finally:
            _power_down(instr)
        if not rows:
            raise RuntimeError("ii: no points")
        mx = max(abs(float(r["II_uA"])) for r in rows)
        return _finish(
            model,
            "ii",
            {
                "summary": f"II n={len(rows)} max_abs={mx:.3f} uA",
                "data": {"rows": rows, "instrument_sense": "DMM-series-input"},
                "measurements": [_meas(model, "II_uA", mx, "uA", test_id="ii")],
            },
        )


def _eval_vcc_minus_tenth(expr: Any, vcc: float) -> Optional[float]:
    """Card formula VCC-0.1 only. Do not invent other expressions."""
    s = str(expr or "").strip().upper().replace(" ", "")
    if s == "VCC-0.1":
        return float(vcc) - 0.1
    return None


def _dc_limit_loads(model: ProductModel, which: str) -> dict[str, Any]:
    dc = model.dc_limits if isinstance(model.dc_limits, dict) else {}
    names = ("VOH", "voh") if which == "voh" else ("VOL", "vol")
    for key in names:
        block = dc.get(key)
        if isinstance(block, dict) and isinstance(block.get("loads"), list) and block["loads"]:
            return block
    return {}


def _expand_voh_vol_loads(model: ProductModel, which: str) -> list[dict[str, Any]]:
    """CONFIRMED dc_limits.VOH/VOL.loads -> Path B rows. Band vcc expands onto merged vcc_list."""
    block = _dc_limit_loads(model, which)
    if not block:
        return []
    st = str(block.get("status") or "").strip().upper().replace("-", "_")
    if st in ("N_A", "NA", "ABSENT"):
        return []
    if not is_datasheet_signed(block.get("status")):
        return []
    loads = block.get("loads") or []
    merged = [float(v) for v in (model.vcc_list or [])]
    i_key = "IOH_mA" if which == "voh" else "IOL_mA"
    spec_v_key = "VOH_min_V" if which == "voh" else "VOL_max_V"
    spec_expr_key = "VOH_min" if which == "voh" else "VOL_max"
    rows: list[dict[str, Any]] = []
    for load in loads:
        if not isinstance(load, dict) or load.get(i_key) is None:
            continue
        try:
            i_a = float(load[i_key]) * 1e-3
        except (TypeError, ValueError):
            continue
        vcc_raw = load.get("vcc")
        vccs: list[float] = []
        if isinstance(vcc_raw, (list, tuple)) and len(vcc_raw) >= 2:
            try:
                lo, hi = float(vcc_raw[0]), float(vcc_raw[1])
            except (TypeError, ValueError):
                continue
            vccs = [v for v in merged if lo - 1e-9 <= v <= hi + 1e-9]
        else:
            try:
                if vcc_raw is not None:
                    vccs = [float(vcc_raw)]
            except (TypeError, ValueError):
                continue
        if not vccs:
            continue
        for vcc in vccs:
            spec: Optional[float] = None
            if load.get(spec_v_key) is not None:
                try:
                    spec = float(load[spec_v_key])
                except (TypeError, ValueError):
                    spec = None
            if spec is None:
                spec = _eval_vcc_minus_tenth(load.get(spec_expr_key), vcc)
            if spec is None:
                continue
            rec: dict[str, Any] = {"vcc": vcc}
            if which == "voh":
                rec["ioh_a"] = i_a
                rec["spec_min"] = spec
            else:
                rec["iol_a"] = i_a
                rec["spec_max"] = spec
            rows.append(rec)
    return rows


def _voh_vol_table(part_key: str, which: str) -> list[dict[str, Any]]:
    model = load_product_model(part_key)
    if model is not None:
        expanded = _expand_voh_vol_loads(model, which)
        if expanded:
            return expanded
    cfg = load_part_yaml(part_key)
    key = "voh_table" if which == "voh" else "vol_table"
    raw = cfg.get(key)
    if isinstance(raw, list) and raw:
        return [r for r in raw if isinstance(r, dict)]
    if model is None:
        return []
    block = model.dc_limits.get(key) or model.dc_limits.get(which)
    if isinstance(block, list):
        return [r for r in block if isinstance(r, dict)]
    return []


def _apply_y_vector(instr, model: ProductModel, high: bool, vcc: float, ilim: float) -> dict[str, str]:
    want = "H" if high else "L"
    vecs = vectors_for_output(model, want, oe_must_be_active=True)
    if not vecs:
        # Fall back: all data high / all-low (may be wrong; mark PROVISIONAL)
        vec = {p: ("H" if high else "L") for p in model.logic_inputs}
        if model.has_oe():
            vec[model.oe_pin] = model.oe_active_level()
        _apply_levels(instr, model, vec, vcc, ilim)
        vec["_status"] = "PROVISIONAL"
        return vec
    chosen = vecs[0]
    want_bits = {p: ("H" if high else "L") for p in model.logic_inputs}
    for v in vecs:
        data = {k: v[k] for k in model.logic_inputs if k in v}
        if data == want_bits:
            chosen = v
            break
    _apply_levels(instr, model, {k: v for k, v in chosen.items() if not str(k).startswith("_")}, vcc, ilim)
    return chosen


def _run_voh_path_b(instr, params: Any) -> dict[str, Any]:
    # INSTRUMENT_SENSE VOH: force Y-high; DMM sense V(Y). Loaded IOH only from voh_table.
    model = _model(params)
    if is_open_drain(model):
        raise RuntimeError(
            "voh: open-drain -- skip VOH series. Y=Z is output OFF, not VOH. "
            "Remove voh from enabled_tests."
        )
    if not voh_series_allowed(model):
        raise RuntimeError(
            "voh: output_type must be push_pull or three_state (CONFIRMED tables). "
            "Remove voh from enabled_tests."
        )
    _require_for(instr, model, "voh")
    with path_b_handoff(params, model, "voh"):
        ilim = _current_limit(params, model)
        key = str(getattr(params, "part", "") or "").lower()
        table = _voh_vol_table(key, "voh")
        rows: list[dict[str, Any]] = []
        meas: list[dict[str, Any]] = []
        try:
            # Loaded IOH hook only when a table already exists (do not invent IOH).
            # No table: unloaded all-high VOH (limits unspec unless limits yaml has them).
            if table:
                from psu_setup import power_off, power_on_protected

                vplus = float(load_part_yaml(key).get("vplus_v") or model.recipe.get("vplus_v") or 0) or None
                for entry in table:
                    vcc = float(entry["vcc"])
                    spec = entry.get("spec_min")
                    ioh = entry.get("ioh_a")
                    if spec is None or ioh is None:
                        rows.append({"VCC": vcc, "status": "PROVISIONAL", "note": "voh_table row missing spec/ioh"})
                        continue
                    vref = entry.get("vref")
                    if vref is None:
                        vref = 0.0  # fixture sink rail; not a datasheet Vref
                    _power_vcc(instr, vcc, ilim)
                    _apply_y_vector(instr, model, True, vcc, ilim)
                    _wait_settled_voltage(instr.dmm, model)
                    if vplus is not None:
                        power_on_protected(instr.psu, 3, float(vplus), ilim)
                    power_on_protected(instr.psu, 2, float(vref), abs(float(ioh)), ocp=max(0.05, abs(float(ioh)) * 1.2))
                    measured = _wait_settled_voltage(instr.dmm, model, setup=False)
                    ok = measured >= float(spec)
                    mid = str(entry.get("id") or f"VOH_{str(vcc).replace('.', 'p')}V")
                    rows.append(
                        {
                            "id": mid,
                            "VCC": vcc,
                            "IOH_A": float(ioh),
                            "Vref": float(vref),
                            "Measured": measured,
                            "Spec_min": float(spec),
                            "Result": "PASS" if ok else "FAIL",
                            "mode": "loaded",
                            "pass_mode": "min_only",
                        }
                    )
                    meas.append(_meas(model, mid, measured, "V", test_id="voh"))
                    power_off(instr.psu)
                    time.sleep(0.3)
            else:
                for vcc in _vcc_corners(params, model):
                    _power_vcc(instr, vcc, ilim)
                    vec = _apply_y_vector(instr, model, True, vcc, ilim)
                    vout = _wait_settled_voltage(instr.dmm, model)
                    rec = {
                        "VCC": vcc,
                        "VOH": vout,
                        "vector": {k: v for k, v in vec.items() if k != "_status"},
                        "mode": "unloaded",
                    }
                    if vec.get("_status"):
                        rec["status"] = vec["_status"]
                    rows.append(rec)
                    tag = str(vcc).replace(".", "p")
                    meas.append(_meas(model, f"VOH_{tag}V", vout, "V", test_id="voh"))
        finally:
            _power_down(instr)
        if not rows:
            raise RuntimeError("voh: no points (no vcc_list / table)")
        return _finish(
            model,
            "voh",
            {
                "summary": f"VOH n={len(rows)} last={rows[-1].get('VOH', rows[-1].get('Measured'))}",
                "data": {
                    "rows": rows,
                    "limits": "existing yaml / voh_table only; else unspec",
                    "instrument_sense": "force-Y / DMM-sense-Vout",
                },
                "measurements": meas,
            },
        )


def _run_vol_path_b(instr, params: Any) -> dict[str, Any]:
    # INSTRUMENT_SENSE VOL: force Y-low; DMM sense V(Y). Loaded IOL only from vol_table.
    model = _model(params)
    _require_for(instr, model, "vol")
    with path_b_handoff(params, model, "vol"):
        ilim = _current_limit(params, model)
        key = str(getattr(params, "part", "") or "").lower()
        table = _voh_vol_table(key, "vol")
        rows: list[dict[str, Any]] = []
        meas: list[dict[str, Any]] = []
        try:
            if table:
                from psu_setup import power_off, power_on_protected

                vplus = float(load_part_yaml(key).get("vplus_v") or model.recipe.get("vplus_v") or 0) or None
                for entry in table:
                    vcc = float(entry["vcc"])
                    spec = entry.get("spec_max")
                    iol = entry.get("iol_a")
                    if spec is None or iol is None:
                        rows.append({"VCC": vcc, "status": "PROVISIONAL", "note": "vol_table row missing spec/iol"})
                        continue
                    vref = entry.get("vref")
                    if vref is None:
                        vref = vcc  # fixture source rail; not a datasheet Vref
                    _power_vcc(instr, vcc, ilim)
                    _apply_y_vector(instr, model, False, vcc, ilim)
                    _wait_settled_voltage(instr.dmm, model)
                    power_on_protected(instr.psu, 2, float(vref), abs(float(iol)), ocp=max(0.05, abs(float(iol)) * 1.2))
                    if vplus is not None:
                        power_on_protected(instr.psu, 3, float(vplus), ilim)
                    measured = _wait_settled_voltage(instr.dmm, model, setup=False)
                    ok = measured <= float(spec)
                    mid = str(entry.get("id") or f"VOL_{str(vcc).replace('.', 'p')}V")
                    rows.append(
                        {
                            "id": mid,
                            "VCC": vcc,
                            "IOL_A": float(iol),
                            "Vref": float(vref),
                            "Measured": measured,
                            "Spec_max": float(spec),
                            "Result": "PASS" if ok else "FAIL",
                            "mode": "loaded",
                            "pass_mode": "max_only",
                        }
                    )
                    meas.append(_meas(model, mid, measured, "V", test_id="vol"))
                    power_off(instr.psu)
                    time.sleep(0.3)
            else:
                for vcc in _vcc_corners(params, model):
                    _power_vcc(instr, vcc, ilim)
                    vec = _apply_y_vector(instr, model, False, vcc, ilim)
                    vout = _wait_settled_voltage(instr.dmm, model)
                    rec = {
                        "VCC": vcc,
                        "VOL": vout,
                        "vector": {k: v for k, v in vec.items() if k != "_status"},
                        "mode": "unloaded",
                    }
                    if vec.get("_status"):
                        rec["status"] = vec["_status"]
                    rows.append(rec)
                    tag = str(vcc).replace(".", "p")
                    meas.append(_meas(model, f"VOL_{tag}V", vout, "V", test_id="vol"))
        finally:
            _power_down(instr)
        if not rows:
            raise RuntimeError("vol: no points")
        return _finish(
            model,
            "vol",
            {
                "summary": f"VOL n={len(rows)} last={rows[-1].get('VOL', rows[-1].get('Measured'))}",
                "data": {
                    "rows": rows,
                    "limits": "existing yaml / vol_table only; else unspec",
                    "instrument_sense": "force-Y / DMM-sense-Vout",
                },
                "measurements": meas,
            },
        )


def _run_ioz(instr, params: Any) -> dict[str, Any]:
    model = _model(params)
    if not model.has_oe():
        raise RuntimeError(
            f"ioz: oe is none on {model.part} -- IOZ is not applicable. "
            "Remove ioz from enabled_tests."
        )
    # INSTRUMENT_SENSE IOZ: OE inactive; DMM in series with Y; PSU CH2 force Vout.
    _require_for(instr, model, "ioz")
    with path_b_handoff(params, model, "ioz"):
        ilim = _current_limit(params, model)
        vccs = _vcc_corners(params, model, "ioz_vcc_list")
        vouts_raw = model.recipe.get("ioz_vout_list")
        rows: list[dict[str, Any]] = []
        try:
            for vcc in vccs:
                _power_vcc(instr, vcc, ilim)
                _wait_settled_current_ua(instr.dmm, model)
                inactive = ioz_force_vector(model)
                _apply_levels(instr, model, inactive, vcc, ilim)
                _wait_settled_current_ua(instr.dmm, model, setup=False)
                if isinstance(vouts_raw, list) and vouts_raw:
                    vouts = [float(x) for x in vouts_raw]
                else:
                    vmax = _vmax_for_ii(model, vcc)
                    vouts = [0.0, float(vmax)]
                for vo in vouts:
                    _force_psu(instr, 2, vo, ilim)
                    i_ua = _wait_settled_current_ua(instr.dmm, model, setup=False)
                    rows.append(
                        {
                            "VCC": vcc,
                            "OE": inactive.get(model.oe_pin) or model.oe_inactive_level(),
                            "VOUT": vo,
                            "IOZ_uA": i_ua,
                        }
                    )
        finally:
            _power_down(instr)
        if not rows:
            raise RuntimeError("ioz: no points")
        mx = max(abs(float(r["IOZ_uA"])) for r in rows)
        return _finish(
            model,
            "ioz",
            {
                "summary": f"IOZ n={len(rows)} max_abs={mx:.3f} uA",
                "data": {"rows": rows, "instrument_sense": "DMM-series-Y / force-Vout"},
                "measurements": [_meas(model, "IOZ_uA", mx, "uA", test_id="ioz")],
            },
        )


def _run_icc_dispatch(instr, params: Any) -> dict[str, Any]:
    return _dispatch_shared("icc", _run_icc, instr, params)


def _run_voh_dispatch(instr, params: Any) -> dict[str, Any]:
    return _dispatch_shared("voh", _run_voh_path_b, instr, params)


def _run_vol_dispatch(instr, params: Any) -> dict[str, Any]:
    return _dispatch_shared("vol", _run_vol_path_b, instr, params)


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
    "input_threshold",
    "Input threshold (VTH)",
    "VTH",
    frozenset({"PSU", "DMM"}),
    _run_input_threshold,
)
_register(
    "vth",
    "VTH",
    "VTH",
    frozenset({"PSU", "DMM"}),
    _run_input_threshold,
)
_register(
    "icc",
    "ICC",
    "Icc",
    frozenset({"PSU", "DMM"}),
    _run_icc_dispatch,
)
_register(
    "delta_icc",
    "Delta ICC",
    "DeltaICC",
    frozenset({"PSU", "DMM"}),
    _run_delta_icc,
)
_register(
    "ii",
    "Input current (II)",
    "II",
    frozenset({"PSU", "DMM"}),
    _run_ii,
)
_register(
    "voh",
    "VOH",
    "VOH",
    frozenset({"PSU", "DMM"}),
    _run_voh_dispatch,
)
_register(
    "vol",
    "VOL",
    "VOL",
    frozenset({"PSU", "DMM"}),
    _run_vol_dispatch,
)
_register(
    "ioz",
    "IOZ (OE inactive)",
    "IOZ",
    frozenset({"PSU", "DMM"}),
    _run_ioz,
)

