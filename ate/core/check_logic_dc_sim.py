"""Visa-free Path B Logic DC SIM. Not a bench green / not a Verify PASS.

Run: python -m ate.core.check_logic_dc_sim

Covers the 17 CONFIRMED Logic product_model SKUs (11 prior + 6 scale-wave
2026-09-21). Overlay one VCC so SIM stays fast. stable_eps_A stays null
(NON_TIGHT). RS1G123 / RS1G74 are dropped/archive PARKED -- not in this
mandatory set. Do not invent limits.
"""
from __future__ import annotations

import re
import sys
from types import SimpleNamespace
from typing import Any, Optional

from ate.core.paths import PARTS_DIR
from ate.core.registry import get, load_family
from ate.fixture.modes import enabled_tests_for_part
from ate.tests.logic import logic_dc as ldc
from ate.tests.logic.product_model import (
    apply_dual_channel_continue,
    dual_channel_continue,
    has_product_model,
    is_open_drain,
    is_parked,
    is_sequential,
    live_session,
    load_product_model,
    recipe_channels,
    voh_series_allowed,
)

_PATH_B_DC = (
    "input_threshold",
    "vth",
    "icc",
    "delta_icc",
    "ii",
    "voh",
    "vol",
    "ioz",
)

# Mandatory Path B SIM set (JH 17 CONFIRMED = 11 prior + 6 scale-wave).
# Sequential skip OK for rs164. PARKED 74/123 stay out.
_ACTIVE_LOGIC = (
    "rs1gt34",
    "rs1g08",
    "rs1g07",
    "rs1g14",
    "rs1g32",
    "rs1gt08",
    "rs1gt32",
    "rs1g125",
    "rs164",
    "rs1g97",
    "rs1g126",
    "rs1g00",
    "rs1g02",
    "rs1g04",
    "rs1g86",
    "rs2g08",
    "rs2g32",
)
# Dropped from Path B scale. Optional UNCONFIRMED archive -- do not block green.
_ARCHIVE_LOGIC = frozenset({"rs1g123", "rs1g74"})
# Scale-wave SKUs (CONFIRMED 2026-09-21). Physics locks; now in mandatory SIM.
_NEXT_WAVE_LOGIC = (
    "rs1g00",
    "rs1g02",
    "rs1g04",
    "rs1g86",
    "rs2g08",
    "rs2g32",
)


def _nosleep(*_a: Any, **_k: Any) -> None:
    return None


def _icct_mapped(model: Any) -> bool:
    return bool(ldc._icct_blob(model)) or (model.recipe or {}).get("delta_offset_v") is not None


def _sim_part_key(model: Any) -> str:
    raw = getattr(model, "raw", None) or {}
    key = str((raw.get("part_key") if isinstance(raw, dict) else "") or getattr(model, "part", "") or "")
    return key.strip().lower()


def applicable_path_b_dc(model: Any) -> list[str]:
    """Physics catalog for this product_model. Sequential is not gate 2^n.

    VOH/VOL join only when CONFIRMED loads / campaign tables exist. Empty
    tables stay fail-closed (do not invent; do not _assert_ran unsigned VOH).
    """
    if is_sequential(model):
        return []
    ids: list[str] = ["vth" if model.schmitt else "input_threshold", "icc"]
    if _icct_mapped(model):
        ids.append("delta_icc")
    ids.append("ii")
    key = _sim_part_key(model)
    if voh_series_allowed(model) and not is_open_drain(model) and ldc._voh_vol_table(key, "voh", model=model):
        ids.append("voh")
    if ldc._voh_vol_table(key, "vol", model=model):
        ids.append("vol")
    if model.has_oe():
        ids.append("ioz")
    return ids


class _Bus:
    def __init__(self, bench: "SimBench", kind: str) -> None:
        self.bench = bench
        self.kind = kind

    def write(self, cmd: str = "", *_a: Any, **_k: Any) -> None:
        self.bench.note_write(self.kind, str(cmd or ""))

    def query(self, cmd: str = "", *_a: Any, **_k: Any) -> str:
        return self.bench.note_query(self.kind, str(cmd or ""))


class SimBench:
    """Mock PSU/DMM/AWG/MSO. Y from truth_table at forced pin volts. Not datasheet numbers."""

    def __init__(self, model: Any) -> None:
        self.model = model
        self.vcc = 3.3
        self.psu_ch: dict[int, float] = {}
        self.awg_ch: dict[int, float] = {}
        self.dmm_mode = "volt"
        self.psu = _Bus(self, "psu")
        self.dmm = _Bus(self, "dmm")
        self.gen = _Bus(self, "awg")
        self.scope = _Bus(self, "mso")

    def note_write(self, kind: str, cmd: str) -> None:
        raw = cmd.strip()
        up = raw.upper()
        if kind == "dmm":
            if "CURR" in up:
                self.dmm_mode = "curr"
            elif "VOLT" in up:
                self.dmm_mode = "volt"
            return
        m = re.search(r":SOUR(\d+):VOLT(?:$|[:\s])\s*([+-]?\d+(?:\.\d+)?)", up)
        if not m:
            m = re.search(r":SOUR(\d+):APPL:DC\s+[^,]*,[^,]*,([+-]?\d+(?:\.\d+)?)", up)
        if not m:
            m = re.search(r":SOUR(\d+):VOLT:OFFS\s+([+-]?\d+(?:\.\d+)?)", up)
        if not m:
            return
        ch = int(m.group(1))
        volts = float(m.group(2))
        if kind == "psu":
            self.psu_ch[ch] = volts
            if ch == 1:
                self.vcc = volts
        elif kind == "awg":
            self.awg_ch[ch] = volts

    def note_query(self, kind: str, _cmd: str) -> str:
        if kind != "dmm":
            return "0"
        if self.dmm_mode == "curr":
            return "4e-7"
        return f"{self._y_v():.6f}"

    def _pin_volts(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for name, drive in (self.model.pin_drive or {}).items():
            src = getattr(drive, "src", "")
            ch = int(getattr(drive, "ch", 0) or 0)
            if src == "psu":
                out[str(name).upper()] = float(self.psu_ch.get(ch, 0.0))
            elif src == "awg":
                out[str(name).upper()] = float(self.awg_ch.get(ch, 0.0))
        return out

    def _levels(self) -> dict[str, str]:
        mid = float(self.vcc) * 0.5
        pins = self._pin_volts()
        lv: dict[str, str] = {}
        for name in self.model.logic_inputs:
            lv[str(name).upper()] = "H" if float(pins.get(str(name).upper(), 0.0)) >= mid else "L"
        if self.model.has_oe():
            oe = str(self.model.oe_pin or "OE").upper()
            lv[oe] = "H" if float(pins.get(oe, 0.0)) >= mid else "L"
        return lv

    def _y_v(self) -> float:
        vcc = float(self.vcc) or 3.3
        want = self._levels()
        y_pin = str(self.model.output_pin or "Y").upper()
        for row in self.model.truth_table or []:
            if not isinstance(row, dict):
                continue
            ok = True
            for pin, bit in want.items():
                cell = str(row.get(pin) or row.get(pin.lower()) or "").strip().upper()
                if cell in ("", "X"):
                    continue
                if cell != bit:
                    ok = False
                    break
            if not ok:
                continue
            y = str(row.get(y_pin) or row.get("Y") or "").strip().upper()
            if y == "H":
                return max(0.0, vcc - 0.05)
            if y == "L":
                return 0.02
            if y in ("Z", "HZ", "HI-Z"):
                return 0.0
        highs = [want.get(p, "L") == "H" for p in self.model.logic_inputs]
        if highs and all(highs):
            return max(0.0, vcc - 0.05)
        return 0.02


def _sim_vcc(model: Any) -> float:
    for cand in (3.3, 3.0, 5.0, 2.0):
        for got in model.vcc_list or []:
            try:
                if abs(float(got) - cand) < 1e-9:
                    return float(got)
            except (TypeError, ValueError):
                continue
    if model.vcc_list:
        try:
            return float(model.vcc_list[0])
        except (TypeError, ValueError):
            pass
    return 3.3


def _overlay(model: Any) -> dict[str, Any]:
    return {
        "vcc_list": [_sim_vcc(model)],
        "recipe": {
            "settle_s": 0.0,
            "settle_timeout_s": 0.2,
            "stable_n": 2,
            "stable_eps_V": 0.05,
        },
    }


def _params(part: str, overlay: dict[str, Any], vcc: float) -> Any:
    return SimpleNamespace(
        part=part,
        vcc=vcc,
        current_limit_a=0.05,
        pause_hook=None,
        test_params=overlay,
    )


def _runner(tid: str):
    if tid == "vth":
        return ldc._run_input_threshold
    spec = get(tid)
    if spec is not None and callable(spec.run):
        return spec.run
    names = {
        "input_threshold": ldc._run_input_threshold,
        "icc": ldc._run_icc,
        "delta_icc": ldc._run_delta_icc,
        "ii": ldc._run_ii,
        "voh": ldc._run_voh_path_b,
        "vol": ldc._run_vol_path_b,
        "ioz": ldc._run_ioz,
    }
    return names.get(tid)


def _patch_sleep() -> list[tuple[Any, str, Any]]:
    import generator_setup
    import psu_setup

    saved: list[tuple[Any, str, Any]] = []
    for mod, attr in (
        (ldc.time, "sleep"),
        (psu_setup.time, "sleep"),
        (generator_setup.time, "sleep"),
    ):
        saved.append((mod, attr, getattr(mod, attr)))
        setattr(mod, attr, _nosleep)
    return saved


def _unpatch(saved: list[tuple[Any, str, Any]]) -> None:
    for mod, attr, old in saved:
        setattr(mod, attr, old)


def _run_one(part: str, tid: str, model: Any) -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
    overlay = _overlay(model)
    vcc = float(overlay["vcc_list"][0])
    sim_model = load_product_model(part, overlay=overlay)
    if sim_model is None:
        return "error", None, "product_model overlay failed"
    bench = SimBench(sim_model)
    instr = SimpleNamespace(psu=bench.psu, dmm=bench.dmm, gen=bench.gen, scope=bench.scope)
    fn = _runner(tid)
    if fn is None:
        return "error", None, f"no runner for {tid}"
    try:
        out = fn(instr, _params(part, overlay, vcc))
        return "ran", out if isinstance(out, dict) else {"raw": out}, None
    except RuntimeError as exc:
        return "raise", None, str(exc)
    except Exception as exc:
        return "error", None, f"{type(exc).__name__}: {exc}"


def _expect_raise(part: str, tid: str, model: Any, needle: str) -> list[str]:
    kind, _out, msg = _run_one(part, tid, model)
    if kind != "raise":
        return [f"{part} SIM {tid}: expected RuntimeError ({needle}), got {kind} {msg!r}"]
    if needle.lower() not in str(msg or "").lower():
        return [f"{part} SIM {tid}: raise must name {needle!r}, got {msg!r}"]
    return []


def _assert_ran(part: str, tid: str, model: Any) -> list[str]:
    kind, out, msg = _run_one(part, tid, model)
    if kind == "error":
        return [f"{part} SIM {tid}: {msg}"]
    if kind == "raise":
        return [f"{part} SIM {tid}: unexpected RuntimeError {msg!r}"]
    data = (out or {}).get("data") if isinstance(out, dict) else {}
    if not isinstance(data, dict):
        return [f"{part} SIM {tid}: missing data"]
    if tid in ("icc", "delta_icc", "ii", "ioz") and data.get("tight_settle_greenable") is True:
        return [f"{part} SIM {tid}: tight-settle must stay FAIL-closed when stable_eps_A is null"]
    if data.get("settle") == "TIGHT":
        return [f"{part} SIM {tid}: settle must be NON_TIGHT (stable_eps_A null)"]
    return []


def check_logic_dc_sim() -> list[str]:
    """SIM the 17 CONFIRMED Logic SKUs. Archive 123/74 do not block green."""
    errors: list[str] = []
    load_family("logic")
    saved = _patch_sleep()
    try:
        if len(_ACTIVE_LOGIC) != 17:
            errors.append(f"_ACTIVE_LOGIC must be the 17 CONFIRMED SKUs, got {len(_ACTIVE_LOGIC)}")
        if _ARCHIVE_LOGIC & set(_ACTIVE_LOGIC):
            errors.append("RS1G123 / RS1G74 archive must not join mandatory SIM set")
        if set(_NEXT_WAVE_LOGIC) - set(_ACTIVE_LOGIC):
            errors.append("scale-wave CONFIRMED must join mandatory SIM set")
        seen: set[str] = set()
        for path in sorted(PARTS_DIR.glob("*.yaml")):
            part = path.stem.lower()
            if part not in _ACTIVE_LOGIC:
                continue
            if not has_product_model(part):
                continue
            seen.add(part)
            m = load_product_model(part)
            if m is None:
                errors.append(f"{part}: product_model failed to load")
                continue
            en = {str(x).strip().lower() for x in (enabled_tests_for_part(part) or [])}
            catalog = applicable_path_b_dc(m)
            if is_sequential(m):
                for banned in ("icc", "delta_icc", "input_threshold", "vth", "voh", "vol", "ioz"):
                    if banned in en:
                        errors.append(f"{part}: sequential must not enable Path B {banned}")
                errors += _expect_raise(part, "icc", m, "sequential")
                errors += _expect_raise(part, "delta_icc", m, "sequential")
                continue
            if is_open_drain(m):
                if "voh" in en or "voh" in catalog:
                    errors.append(f"{part}: open-drain must skip VOH")
                errors += _expect_raise(part, "voh", m, "open-drain")
            if not m.has_oe() and "ioz" in en:
                errors.append(f"{part}: oe none must not enable ioz")
            if part in _NEXT_WAVE_LOGIC:
                for banned in ("voh", "vol", "ioz", "delta_icc"):
                    if banned in en:
                        errors.append(f"{part}: invent {banned} enabled -> FAIL")
                if part in ("rs2g08", "rs2g32"):
                    if not dual_channel_continue(m):
                        errors.append(f"{part}: dual_channel_continue CHA then CHB required")
                    elif recipe_channels(m) != ["CHA", "CHB"]:
                        errors.append(f"{part}: skip CHA->CHB -> FAIL, got {recipe_channels(m)}")
                    else:
                        specs = [get(tid) for tid in catalog]
                        specs = [s for s in specs if s is not None]
                        over = apply_dual_channel_continue(specs, m)
                        if any(not getattr(s, "dual_channel", False) for s in over):
                            errors.append(
                                f"{part}: CHA->CHB Continue must OR dual_channel onto Path B specs"
                            )
            run_ids = list(catalog)
            if "vth" in run_ids and "input_threshold" in run_ids:
                run_ids = [x for x in run_ids if x != "vth"]
            for tid in run_ids:
                errors += _assert_ran(part, tid, m)
            if part == "rs1g07":
                live = live_session(m)
                voh_l = live.get("voh") if isinstance(live.get("voh"), dict) else {}
                if voh_l.get("rows") or voh_l.get("loads"):
                    errors.append("rs1g07 must not invent VOH live")
            if part == "rs1gt34":
                live = live_session(m)
                vol_l = live.get("vol") if isinstance(live.get("vol"), dict) else {}
                if str(vol_l.get("status") or "").upper().replace("-", "_") != "NOT_RUN":
                    errors.append("rs1gt34 live.vol must stay NOT_RUN (no VOL live this turn)")
                if vol_l.get("measured") is not None or vol_l.get("rows"):
                    errors.append("rs1gt34 must not invent VOL live measured")
        for part in _ACTIVE_LOGIC:
            if not has_product_model(part):
                errors.append(f"{part}: product_model missing (17 CONFIRMED SIM)")
        missing = [p for p in _ACTIVE_LOGIC if p not in seen]
        if missing:
            errors.append(f"SIM missed active parts {missing}")
    finally:
        _unpatch(saved)
    return errors


def part_sim_status() -> list[dict[str, Any]]:
    """Ready / Not ready rows for operator. SIM only -- not bench green."""
    rows: list[dict[str, Any]] = []
    load_family("logic")
    saved = _patch_sleep()
    try:
        for part in _ACTIVE_LOGIC:
            m = load_product_model(part) if has_product_model(part) else None
            if m is None:
                rows.append(
                    {
                        "part": part,
                        "ready": "Not ready",
                        "reason": "no product_model",
                    }
                )
                continue
            if is_sequential(m):
                st = str(m.status or "")
                parked = "PARKED; " if is_parked(m) else ""
                rows.append(
                    {
                        "part": part,
                        "ready": "PARKED (sequential)" if is_parked(m) else "SIM skip (sequential)",
                        "reason": (
                            f"{parked}not combinational 2^n; status={st or 'UNCONFIRMED'}; "
                            "Path B gate DC off"
                        ),
                    }
                )
                continue
            catalog = applicable_path_b_dc(m)
            fails: list[str] = []
            run_ids = [x for x in catalog if not (x == "vth" and "input_threshold" in catalog)]
            if is_open_drain(m):
                fails += _expect_raise(part, "voh", m, "open-drain")
            for tid in run_ids:
                fails += _assert_ran(part, tid, m)
            if fails:
                rows.append(
                    {
                        "part": part,
                        "ready": "Not ready",
                        "reason": fails[0],
                    }
                )
            else:
                extra = "G07 VOH SKIP N_A. " if part == "rs1g07" else ""
                if part == "rs1gt34":
                    extra += "VOL live NOT_RUN. "
                if part in _NEXT_WAVE_LOGIC:
                    extra += "unsigned VOH/VOL/ICCT HOLD. "
                if part in ("rs2g08", "rs2g32"):
                    extra += "CHA then CHB Continue. "
                rows.append(
                    {
                        "part": part,
                        "ready": "SIM green",
                        "reason": extra + "visa-free Path B catalog; not bench green",
                    }
                )
        for part in sorted(_ARCHIVE_LOGIC):
            m = load_product_model(part) if has_product_model(part) else None
            if m is not None and is_parked(m):
                rows.append(
                    {
                        "part": part,
                        "ready": "PARKED",
                        "reason": (
                            "JH dropped; UNCONFIRMED archive; sequential -- "
                            "FAIL if treated as gate 2^n"
                        ),
                    }
                )
            else:
                rows.append(
                    {
                        "part": part,
                        "ready": "dropped/archive",
                        "reason": "optional UNCONFIRMED stub; not Path B scale; no invent VT+/- / gate 2^n",
                    }
                )
        for part in _NEXT_WAVE_LOGIC:
            if part in _ACTIVE_LOGIC:
                continue
            m = load_product_model(part) if has_product_model(part) else None
            if m is None:
                rows.append(
                    {
                        "part": part,
                        "ready": "UNCONFIRMED (numbers HOLD)",
                        "reason": "next-wave bind missing; not Datasheet-signed; not bench green",
                    }
                )
                continue
            rows.append(
                {
                    "part": part,
                    "ready": "UNCONFIRMED (numbers HOLD)",
                    "reason": "Path B process only; not Datasheet-signed; not bench green",
                }
            )
    finally:
        _unpatch(saved)
    return rows


def main() -> int:
    errors = check_logic_dc_sim()
    rows = part_sim_status()
    print("Logic 17 CONFIRMED SIM (visa-free; not a Verify PASS / not bench green)")
    for row in rows:
        print(f"  {row['part']}: {row['ready']} -- {row['reason']}")
    if errors:
        print("FAIL logic-dc SIM:")
        for line in errors:
            print(f"  - {line}")
        return 1
    print("OK logic-dc SIM: Path B catalog ran visa-free (NON_TIGHT; no invent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
