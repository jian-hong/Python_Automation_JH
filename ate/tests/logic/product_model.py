"""Path B Logic product-model loader (schema in YAML, not per-chip Python).

Isolation is derived from truth_table unless the part YAML supplies an
explicit isolation block. Do not branch on part name. RS1G97 table is the
datasheet extract (not a C-select MUX). See Lim goldens are not loaded here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import yaml

from ate.core.paths import PARTS_DIR

_H = frozenset({"H", "1", "TRUE", "HIGH"})
_L = frozenset({"L", "0", "FALSE", "LOW"})
_Z = frozenset({"Z", "HZ", "HIZ", "HI-Z"})
_X = frozenset({"X", "DC", "DONTCARE", "DON'T-CARE"})


def _norm_level(raw: Any) -> str:
    if raw is None:
        return "X"
    if isinstance(raw, bool):
        return "H" if raw else "L"
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw == 1:
            return "H"
        if raw == 0:
            return "L"
    s = str(raw).strip().upper().replace(" ", "")
    if s in _H:
        return "H"
    if s in _L:
        return "L"
    if s in _Z:
        return "Z"
    if s in _X:
        return "X"
    return s


def _bit(level: str) -> Optional[int]:
    lv = _norm_level(level)
    if lv == "H":
        return 1
    if lv == "L":
        return 0
    return None


@dataclass(frozen=True)
class Pin:
    name: str
    role: str  # input | output | oe | vcc | gnd | nc


@dataclass(frozen=True)
class DriveMap:
    src: str  # awg | psu
    ch: int


@dataclass(frozen=True)
class IsolationPattern:
    sweep_pin: str
    fix: dict[str, str]
    y_expect: str  # track | invert
    vil_sweep: str = "rising_then_falling"  # reverse = falling-first for VIL
    status: str = ""


@dataclass
class ProductModel:
    part: str
    pins: list[Pin]
    logic_inputs: list[str]
    oe_mode: str  # none | high | low
    oe_pin: str
    schmitt: bool
    vcc_list: list[float]
    vcc_op_min: Optional[float]
    vcc_op_max: Optional[float]
    truth_table: list[dict[str, str]]
    truth_table_status: str
    isolation: dict[str, list[IsolationPattern]]
    isolation_status: str
    dc_limits: dict[str, Any]
    limit_mode: dict[str, str]
    pin_drive: dict[str, DriveMap]
    recipe: dict[str, Any]
    output_pin: str = "Y"
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def has_oe(self) -> bool:
        return self.oe_mode in ("high", "low")

    def oe_active_level(self) -> str:
        return oe_active_level(self.oe_mode)

    def oe_inactive_level(self) -> str:
        return oe_inactive_level(self.oe_mode)


def _as_dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _as_list(raw: Any) -> list[Any]:
    return list(raw) if isinstance(raw, list) else []


def load_part_yaml(part_key: str) -> dict[str, Any]:
    key = str(part_key or "").strip().lower()
    if not key:
        return {}
    path = PARTS_DIR / f"{key}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_product_model_dict(part_key: str) -> dict[str, Any]:
    """Return the product_model mapping, or {} if this part is not Path B.

    Adjacent file: ate/config/parts/<key>.model.yaml (optional). Inline
    `product_model:` in the part YAML wins on overlapping keys.
    """
    key = str(part_key or "").strip().lower()
    if not key:
        return {}
    merged: dict[str, Any] = {}
    adj = PARTS_DIR / f"{key}.model.yaml"
    if adj.is_file():
        blob = yaml.safe_load(adj.read_text(encoding="utf-8")) or {}
        if isinstance(blob, dict):
            inner = blob.get("product_model") if isinstance(blob.get("product_model"), dict) else blob
            if isinstance(inner, dict):
                merged.update(inner)
    part = load_part_yaml(key)
    inline = part.get("product_model")
    if isinstance(inline, dict):
        merged.update(inline)
    return merged


def has_product_model(part_key: str) -> bool:
    blob = load_product_model_dict(part_key)
    return bool(blob.get("logic_inputs") or blob.get("pins") or blob.get("truth_table"))


def _pins(blob: dict[str, Any]) -> list[Pin]:
    out: list[Pin] = []
    for row in _as_list(blob.get("pins")):
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip().upper()
        role = str(row.get("role") or "").strip().lower()
        if name:
            out.append(Pin(name=name, role=role or "input"))
    return out


def _logic_inputs(blob: dict[str, Any], pins: list[Pin]) -> list[str]:
    raw = blob.get("logic_inputs")
    if isinstance(raw, list) and raw:
        return [str(x).strip().upper() for x in raw if str(x).strip()]
    return [p.name for p in pins if p.role == "input"]


def oe_active_level(oe_mode: str) -> str:
    return "L" if oe_mode == "low" else "H"


def oe_inactive_level(oe_mode: str) -> str:
    return "H" if oe_mode == "low" else "L"


def _oe(blob: dict[str, Any], pins: list[Pin]) -> tuple[str, str]:
    raw = blob.get("oe")
    oe_pin = next((p.name for p in pins if p.role == "oe"), "OE")
    if raw in (None, "", "none", "None", False):
        return "none", oe_pin
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("none", "no", "off"):
            return "none", oe_pin
        if s in ("high", "h", "active_high", "active-high"):
            return "high", oe_pin
        if s in ("low", "l", "active_low", "active-low"):
            return "low", oe_pin
        return "none", oe_pin
    if isinstance(raw, dict):
        pin = str(raw.get("pin") or oe_pin).strip().upper() or oe_pin
        active = raw.get("active", raw.get("mode", raw.get("level")))
        if active in (None, "", "none"):
            return "none", pin
        s = str(active).strip().lower()
        if s in ("none", "no"):
            return "none", pin
        if s in ("high", "h", "1"):
            return "high", pin
        if s in ("low", "l", "0"):
            return "low", pin
        return "none", pin
    return "none", oe_pin


def _floats(raw: Any) -> list[float]:
    out: list[float] = []
    for x in _as_list(raw):
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            continue
    return out


def _vcc_list(blob: dict[str, Any], part_yaml: dict[str, Any]) -> list[float]:
    for key in ("vcc_list", "vcc_sweep_list", "vcc_sweep"):
        nums = _floats(blob.get(key))
        if nums:
            return nums
    nums = _floats(part_yaml.get("vcc_list") or part_yaml.get("vcc_sweep_list") or part_yaml.get("vcc_sweep"))
    if nums:
        return nums
    try:
        if part_yaml.get("vcc") is not None:
            return [float(part_yaml["vcc"])]
    except (TypeError, ValueError):
        pass
    return []


def _opt_float(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _truth_rows(blob: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    raw = blob.get("truth_table")
    status = ""
    rows_in: list[Any]
    if isinstance(raw, dict):
        status = str(raw.get("status") or "")
        rows_in = _as_list(raw.get("rows") or raw.get("table"))
    else:
        rows_in = _as_list(raw)
    rows: list[dict[str, str]] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        item = {str(k).strip().upper(): _norm_level(v) for k, v in row.items()}
        if item:
            rows.append(item)
    return rows, status


def _lookup_y(
    rows: list[dict[str, str]],
    vector: dict[str, str],
    output_pin: str,
) -> Optional[str]:
    """Match a truth row. X in the table is don't-care; Z is Hi-Z."""
    want = {k.upper(): _norm_level(v) for k, v in vector.items()}
    for row in rows:
        ok = True
        for pin, lv in want.items():
            cell = row.get(pin)
            if cell is None:
                continue
            if cell in ("X",):
                continue
            if _norm_level(cell) != lv:
                ok = False
                break
        if ok:
            y = row.get(output_pin.upper())
            if y is not None:
                return _norm_level(y)
    return None


def derive_isolation(
    *,
    logic_inputs: list[str],
    truth_table: list[dict[str, str]],
    output_pin: str = "Y",
    oe_pin: str = "",
    oe_active: str = "",
) -> dict[str, list[IsolationPattern]]:
    """Unused ties so Y tracks or inverts the swept pin. No part-name branches."""
    if not logic_inputs or not truth_table:
        return {}
    out: dict[str, list[IsolationPattern]] = {}
    others_base = list(logic_inputs)
    for sweep in logic_inputs:
        others = [p for p in others_base if p != sweep]
        n = len(others)
        patterns: list[IsolationPattern] = []
        for mask in range(1 << n) if n else [0]:
            fix: dict[str, str] = {}
            for i, pin in enumerate(others):
                fix[pin] = "H" if (mask >> i) & 1 else "L"
            if oe_pin and oe_active:
                fix[oe_pin] = oe_active
            vec_l = dict(fix)
            vec_h = dict(fix)
            vec_l[sweep] = "L"
            vec_h[sweep] = "H"
            y_l = _lookup_y(truth_table, vec_l, output_pin)
            y_h = _lookup_y(truth_table, vec_h, output_pin)
            if y_l in (None, "Z", "X") or y_h in (None, "Z", "X"):
                continue
            if y_l == "L" and y_h == "H":
                patterns.append(
                    IsolationPattern(
                        sweep_pin=sweep,
                        fix=dict(fix),
                        y_expect="track",
                    )
                )
            elif y_l == "H" and y_h == "L":
                patterns.append(
                    IsolationPattern(
                        sweep_pin=sweep,
                        fix=dict(fix),
                        y_expect="invert",
                        vil_sweep="reverse",
                    )
                )
        out[sweep] = patterns
    return out


def _parse_isolation_block(raw: Any) -> tuple[dict[str, list[IsolationPattern]], str]:
    if not isinstance(raw, dict) or not raw:
        return {}, ""
    status = str(raw.get("status") or "")
    tests = raw.get("tests") if isinstance(raw.get("tests"), dict) else raw
    out: dict[str, list[IsolationPattern]] = {}
    for key, val in tests.items() if isinstance(tests, dict) else []:
        if str(key).strip().lower() in ("status", "note", "notes"):
            continue
        pin = str(key).strip().upper()
        rows = val if isinstance(val, list) else [val]
        pats: list[IsolationPattern] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            sweep = str(row.get("sweep_pin") or pin).strip().upper()
            fix_raw = row.get("fix") if isinstance(row.get("fix"), dict) else {}
            fix = {str(k).strip().upper(): _norm_level(v) for k, v in fix_raw.items()}
            expect = str(row.get("y_expect") or row.get("expect") or "track").strip().lower()
            if expect not in ("track", "invert"):
                expect = "track"
            vil = str(row.get("vil_sweep") or "").strip().lower()
            if expect == "invert" and not vil:
                vil = "reverse"
            if not vil:
                vil = "rising_then_falling"
            pats.append(
                IsolationPattern(
                    sweep_pin=sweep,
                    fix=fix,
                    y_expect=expect,
                    vil_sweep=vil,
                    status=str(row.get("status") or status),
                )
            )
        if pats:
            out[pin] = pats
    return out, status


def _pin_drive(blob: dict[str, Any], logic_inputs: list[str], oe_pin: str, oe_mode: str) -> dict[str, DriveMap]:
    """Stimulus map from YAML. Default: AWG ch = 1..n in logic_inputs order.

    Extra pins after two AWG channels default to PSU CH2, CH3 (PROVISIONAL).
    """
    out: dict[str, DriveMap] = {}
    raw = blob.get("pin_drive") if isinstance(blob.get("pin_drive"), dict) else {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        src = str(spec.get("src") or spec.get("instrument") or "awg").strip().lower()
        if src not in ("awg", "psu"):
            src = "awg"
        try:
            ch = int(spec.get("ch") or spec.get("channel") or 1)
        except (TypeError, ValueError):
            ch = 1
        out[str(name).strip().upper()] = DriveMap(src=src, ch=ch)
    names = list(logic_inputs)
    if oe_mode != "none" and oe_pin and oe_pin not in names:
        names.append(oe_pin)
    awg_ch = 1
    psu_ch = 2
    for name in names:
        if name in out:
            continue
        if awg_ch <= 2:
            out[name] = DriveMap(src="awg", ch=awg_ch)
            awg_ch += 1
        else:
            out[name] = DriveMap(src="psu", ch=psu_ch)
            psu_ch += 1
    return out


def load_product_model(part_key: str) -> Optional[ProductModel]:
    key = str(part_key or "").strip().lower()
    blob = load_product_model_dict(key)
    if not blob:
        return None
    part_yaml = load_part_yaml(key)
    pins = _pins(blob)
    logic_inputs = _logic_inputs(blob, pins)
    if not logic_inputs and not pins:
        return None
    oe_mode, oe_pin = _oe(blob, pins)
    schmitt = bool(blob.get("schmitt"))
    vcc_list = _vcc_list(blob, part_yaml)
    vcc_op_min = _opt_float(blob.get("vcc_op_min") or blob.get("vcc_min"))
    vcc_op_max = _opt_float(blob.get("vcc_op_max") or blob.get("vcc_max"))
    if vcc_op_min is None:
        vcc_op_min = _opt_float(part_yaml.get("vcc_op_min"))
    if vcc_op_max is None:
        vcc_op_max = _opt_float(part_yaml.get("vcc_op_max"))
    truth_table, tt_status = _truth_rows(blob)
    output_pin = str(blob.get("output_pin") or "Y").strip().upper() or "Y"
    for p in pins:
        if p.role == "output":
            output_pin = p.name
            break
    explicit, iso_status = _parse_isolation_block(blob.get("isolation"))
    derived = derive_isolation(
        logic_inputs=logic_inputs,
        truth_table=truth_table,
        output_pin=output_pin,
        oe_pin=oe_pin if oe_mode != "none" else "",
        oe_active=oe_active_level(oe_mode) if oe_mode != "none" else "",
    )
    isolation = explicit if explicit else derived
    dc_limits = _as_dict(blob.get("dc_limits"))
    limit_mode_raw = blob.get("limit_mode")
    limit_mode = (
        {str(k): str(v) for k, v in limit_mode_raw.items()}
        if isinstance(limit_mode_raw, dict)
        else {}
    )
    recipe = _as_dict(blob.get("recipe"))
    pin_drive = _pin_drive(blob, logic_inputs, oe_pin, oe_mode)
    part_name = str(blob.get("part") or part_yaml.get("part") or key).strip()
    return ProductModel(
        part=part_name or key,
        pins=pins,
        logic_inputs=logic_inputs,
        oe_mode=oe_mode,
        oe_pin=oe_pin,
        schmitt=schmitt,
        vcc_list=vcc_list,
        vcc_op_min=vcc_op_min,
        vcc_op_max=vcc_op_max,
        truth_table=truth_table,
        truth_table_status=tt_status,
        isolation=isolation,
        isolation_status=iso_status or str(blob.get("isolation_status") or ""),
        dc_limits=dc_limits,
        limit_mode=limit_mode,
        pin_drive=pin_drive,
        recipe=recipe,
        output_pin=output_pin,
        status=str(blob.get("status") or ""),
        raw=blob,
    )


def logic_volts(level: Any, vcc: float) -> float:
    lv = _norm_level(level)
    if lv == "H":
        return float(vcc)
    return 0.0


def icc_pins(model: ProductModel) -> list[str]:
    """Data pins, plus OE when present (ICC over data x OE space)."""
    pins = list(model.logic_inputs)
    if model.has_oe() and model.oe_pin and model.oe_pin not in pins:
        pins.append(model.oe_pin)
    return pins


def iter_logic_corners(pins: Iterable[str]) -> list[dict[str, str]]:
    names = [str(p).strip().upper() for p in pins if str(p).strip()]
    n = len(names)
    if not n:
        return [{}]
    out: list[dict[str, str]] = []
    for mask in range(1 << n):
        row = {names[i]: ("H" if (mask >> i) & 1 else "L") for i in range(n)}
        out.append(row)
    return out


def vectors_for_output(
    model: ProductModel,
    y_level: str,
    *,
    oe_must_be_active: bool = True,
) -> list[dict[str, str]]:
    """Truth-table input vectors that produce Y=y_level. Empty if unknown."""
    want = _norm_level(y_level)
    rows: list[dict[str, str]] = []
    extra: dict[str, str] = {}
    if oe_must_be_active and model.has_oe():
        extra[model.oe_pin] = model.oe_active_level()
    if not model.truth_table:
        return []
    pins = list(model.logic_inputs)
    for vec in iter_logic_corners(pins):
        full = dict(vec)
        full.update(extra)
        y = _lookup_y(model.truth_table, full, model.output_pin)
        if y == want:
            rows.append(full)
    return rows


def isolation_for(model: ProductModel, sweep_pin: str) -> list[IsolationPattern]:
    key = str(sweep_pin).strip().upper()
    return list(model.isolation.get(key) or [])
