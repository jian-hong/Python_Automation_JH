"""Path B Logic product-model loader (schema in YAML, not per-chip Python).

Isolation is derived from truth_table unless the part YAML supplies an
explicit isolation block. Do not branch on part name.

truth_table.status UNCONFIRMED / HOLD_CONFIRM / PROVISIONAL is not
Datasheet-signed. Runtime must not report those tables as confirmed or green.
See Lim goldens are not loaded here.
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

# Datasheet-signed is the only greenable token. CONFIRM alone is not signed.
_SIGNED_STATUSES = frozenset(
    {
        "DATASHEET-SIGNED",
        "DATASHEET_SIGNED",
        "DATASHEET-SIGNED CONFIRM",
        "DATASHEET_SIGNED_CONFIRM",
        "DATASHEET-SIGNED-CONFIRM",
    }
)
_UNCONFIRMED_STATUSES = frozenset(
    {
        "UNCONFIRMED",
        "HOLD_CONFIRM",
        "HOLD-CONFIRM",
        "PROVISIONAL",
        "UNSURE",
        "OCR",
        "OCR-FIT",
        "REVERSE-ENGINEERED",
    }
)
_PASS_MODES = frozenset({"range", "min_only", "max_only"})


def _norm_status(raw: Any) -> str:
    return " ".join(str(raw or "").strip().upper().replace("_", "-").split())


def is_datasheet_signed(status: Any) -> bool:
    s = _norm_status(status)
    compact = s.replace(" ", "-")
    return s in _SIGNED_STATUSES or compact in _SIGNED_STATUSES


def is_unconfirmed_status(status: Any) -> bool:
    """Not greenable. Empty counts as UNCONFIRMED (fail-closed)."""
    if is_datasheet_signed(status):
        return False
    s = _norm_status(status)
    if not s:
        return True
    token = s.replace(" ", "-")
    if s in _UNCONFIRMED_STATUSES or token in _UNCONFIRMED_STATUSES:
        return True
    if "UNCONFIRMED" in s or "PROVISIONAL" in s or "HOLD-CONFIRM" in token:
        return True
    return False


def claimed_signed_without_datasheet(status: Any) -> bool:
    """CONFIRM / SIGNED / from_datasheet without the Datasheet-signed token."""
    if is_datasheet_signed(status):
        return False
    s = _norm_status(status)
    if not s:
        return False
    if s in ("CONFIRM", "CONFIRMED", "SIGNED", "DATASHEET"):
        return True
    if s.startswith("CONFIRM") or s == "GREEN":
        return True
    return False


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
    number: Optional[int] = None


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
    pass_mode: dict[str, str]
    pin_drive: dict[str, DriveMap]
    recipe: dict[str, Any]
    output_pin: str = "Y"
    status: str = ""
    vcc_list_status: str = ""
    vcc_op_status: str = ""
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
        num = row.get("number", row.get("pin", row.get("pkg_pin")))
        pin_no: Optional[int] = None
        try:
            if num is not None and num != "":
                pin_no = int(num)
        except (TypeError, ValueError):
            pin_no = None
        if name:
            out.append(Pin(name=name, role=role or "input", number=pin_no))
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
    """Sweep corners from YAML lists only. Never expand vcc_op_min/max."""
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
    status = str(blob.get("truth_table_status") or "")
    rows_in: list[Any]
    if isinstance(raw, dict):
        status = str(raw.get("status") or status)
        rows_in = _as_list(raw.get("rows") or raw.get("table"))
    else:
        rows_in = _as_list(raw)
    if not status:
        status = "UNCONFIRMED"
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


def _coerce_pass_mode(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace("-", "_")
    if s in _PASS_MODES:
        return s
    return ""


def _pass_mode(blob: dict[str, Any], schmitt: bool) -> dict[str, str]:
    """pass_mode wins; limit_mode is an alias. Do not collapse plain VIH/VIL to range."""
    out: dict[str, str] = {}
    for src in (blob.get("limit_mode"), blob.get("pass_mode")):
        if not isinstance(src, dict):
            continue
        for key, val in src.items():
            mode = _coerce_pass_mode(val)
            if mode:
                out[str(key).strip()] = mode
    # Schmitt VT+/VT- are range. Do not invent a single input_threshold:range for plain parts.
    if schmitt:
        if "VT+" not in out and "VTPLUS" not in out and "VTPLUS_V" not in out:
            if out.get("input_threshold") == "range":
                out["VT+"] = "range"
                out["VT-"] = "range"
    else:
        # Drop a collapsed input_threshold:range so callers must use VIH/VIL.
        if "VIH" not in out and "VIH_V" not in out:
            out.setdefault("VIH", "min_only")
        if "VIL" not in out and "VIL_V" not in out:
            out.setdefault("VIL", "max_only")
    return out


def lookup_pass_mode(model: ProductModel, meas_id: str, test_id: str = "") -> str:
    """Resolve pass_mode for one measurement id. Empty = judge both min and max."""
    table = dict(model.pass_mode or model.limit_mode or {})
    if not table:
        return ""
    mid = str(meas_id or "").strip()
    tid = str(test_id or "").strip().lower()
    keys = [
        mid,
        mid.upper(),
        mid.replace("_", ""),
        tid,
    ]
    if mid.upper() in ("VTPLUS_V", "VT+", "VTPLUS"):
        keys.extend(["VT+", "VTPLUS", "VTPLUS_V", "input_threshold", "vth"])
    if mid.upper() in ("VTMINUS_V", "VT-", "VTMINUS"):
        keys.extend(["VT-", "VTMINUS", "VTMINUS_V", "input_threshold", "vth"])
    if mid.upper() in ("VIH_V", "VIH"):
        keys.extend(["VIH", "VIH_V"])
    if mid.upper() in ("VIL_V", "VIL"):
        keys.extend(["VIL", "VIL_V"])
    if mid.upper() in ("ICC_UA", "ICC"):
        keys.extend(["icc", "ICC"])
    if mid.upper() in ("DELTA_ICC_UA", "DELTA_ICC"):
        keys.extend(["delta_icc", "DELTA_ICC"])
    if mid.upper() in ("II_UA", "II"):
        keys.extend(["ii", "II"])
    if mid.upper() in ("IOZ_UA", "IOZ"):
        keys.extend(["ioz", "IOZ"])
    if mid.upper().startswith("VOH"):
        keys.extend(["voh", "VOH"])
    if mid.upper().startswith("VOL"):
        keys.extend(["vol", "VOL"])
    for key in keys:
        if not key:
            continue
        for cand in (key, str(key).lower(), str(key).upper()):
            mode = _coerce_pass_mode(table.get(cand))
            if mode:
                return mode
    return ""


def model_gaps(model: ProductModel) -> list[str]:
    """Operator-visible PROVISIONAL / UNCONFIRMED holes. Not a green stamp."""
    gaps: list[str] = []
    if is_unconfirmed_status(model.truth_table_status):
        gaps.append(
            f"truth_table.status={model.truth_table_status or 'UNCONFIRMED'} "
            "(not Datasheet-signed; not greenable)"
        )
    if is_unconfirmed_status(model.isolation_status):
        gaps.append(
            f"isolation.status={model.isolation_status or 'UNCONFIRMED'} "
            "(not Datasheet-signed)"
        )
    if claimed_signed_without_datasheet(model.truth_table_status):
        gaps.append(
            f"truth_table.status={model.truth_table_status!r} claims confirm without Datasheet-signed"
        )
    vcc_st = model.vcc_list_status or ""
    if is_unconfirmed_status(vcc_st) or _norm_status(vcc_st) in ("PROVISIONAL", "RANGE-METADATA"):
        gaps.append(
            f"vcc_list={model.vcc_list} status={vcc_st or 'held'}; "
            "vcc_op_min/max are range metadata only"
        )
    else:
        gaps.append(
            f"vcc_op {model.vcc_op_min}..{model.vcc_op_max} is range metadata "
            f"({model.vcc_op_status or 'RANGE_METADATA'}); sweep is vcc_list only"
        )
    for name, block in (model.dc_limits or {}).items():
        if isinstance(block, dict) and is_unconfirmed_status(block.get("status")):
            gaps.append(f"{name}: {block.get('status')} ({block.get('note') or 'no invented loads'})")
    if not model.has_oe():
        gaps.append("oe=none: IOZ not applicable (do not enable ioz/ioff)")
    return gaps


def panel_payload(part_key: str) -> dict[str, Any]:
    """Minimal Logic DC editor payload. Empty present=false when no product_model."""
    key = str(part_key or "").strip().lower()
    model = load_product_model(key)
    if model is None:
        return {"present": False, "part": key, "gaps": []}
    blob = load_product_model_dict(key)
    tt = blob.get("truth_table") if isinstance(blob.get("truth_table"), dict) else {
        "status": model.truth_table_status,
        "rows": model.truth_table,
    }
    iso = blob.get("isolation") if isinstance(blob.get("isolation"), dict) else {
        "status": model.isolation_status,
        "tests": {
            pin: [
                {
                    "sweep_pin": p.sweep_pin,
                    "fix": dict(p.fix),
                    "y_expect": p.y_expect,
                    "vil_sweep": p.vil_sweep,
                    "status": p.status,
                }
                for p in pats
            ]
            for pin, pats in model.isolation.items()
        },
    }
    return {
        "present": True,
        "part": model.part,
        "part_key": key,
        "truth_table_status": model.truth_table_status,
        "isolation_status": model.isolation_status,
        "greenable": is_datasheet_signed(model.truth_table_status)
        and not is_unconfirmed_status(model.isolation_status),
        "schmitt": model.schmitt,
        "oe": model.oe_mode,
        "vcc_list": list(model.vcc_list),
        "vcc_list_status": model.vcc_list_status,
        "vcc_op_min": model.vcc_op_min,
        "vcc_op_max": model.vcc_op_max,
        "vcc_op_status": model.vcc_op_status,
        "pass_mode": dict(model.pass_mode),
        "limit_mode": dict(model.limit_mode),
        "truth_table": tt,
        "isolation": iso,
        "gaps": model_gaps(model),
        "pins": [{"name": p.name, "role": p.role, "number": p.number} for p in model.pins],
    }


_PANEL_SAVE_KEYS = (
    "truth_table",
    "isolation",
    "pass_mode",
    "limit_mode",
    "vcc_list",
    "vcc_list_status",
    "truth_table_status",
    "isolation_status",
)


def save_product_model_fields(part_key: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Write editable Path B fields back to part YAML. Cannot promote to Datasheet-signed."""
    key = str(part_key or "").strip().lower()
    path = PARTS_DIR / f"{key}.yaml"
    if not path.is_file():
        raise RuntimeError(f"part yaml missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"part yaml is not a mapping: {path}")
    pm = data.get("product_model")
    if not isinstance(pm, dict):
        raise RuntimeError(f"{key}: no product_model block to edit")
    before = load_product_model(key)
    if before is None:
        raise RuntimeError(f"{key}: product_model failed to load")
    if not isinstance(patch, dict):
        raise RuntimeError("save_product_model: patch must be a mapping")
    for field in _PANEL_SAVE_KEYS:
        if field not in patch:
            continue
        val = patch[field]
        if field == "vcc_list":
            nums = _floats(val) if not isinstance(val, (int, float)) else [float(val)]
            if not nums:
                continue
            # Do not expand inventively: keep existing length unless operator edits YAML list.
            pm["vcc_list"] = nums
            continue
        if field in ("truth_table_status", "isolation_status"):
            if is_datasheet_signed(val) and not is_datasheet_signed(
                before.truth_table_status if field == "truth_table_status" else before.isolation_status
            ):
                raise RuntimeError(
                    "Panel cannot promote status to Datasheet-signed. "
                    "Hand-edit YAML after a signed datasheet confirm."
                )
            pm[field] = val
            if field == "truth_table_status" and isinstance(pm.get("truth_table"), dict):
                pm["truth_table"]["status"] = val
            if field == "isolation_status" and isinstance(pm.get("isolation"), dict):
                pm["isolation"]["status"] = val
            continue
        if field in ("truth_table", "isolation") and isinstance(val, dict):
            nested = dict(val)
            st = nested.get("status")
            if is_datasheet_signed(st) and not is_datasheet_signed(
                before.truth_table_status if field == "truth_table" else before.isolation_status
            ):
                raise RuntimeError(
                    "Panel cannot promote truth_table/isolation to Datasheet-signed."
                )
            if field == "truth_table" and is_unconfirmed_status(before.truth_table_status):
                nested["status"] = before.truth_table_status or "UNCONFIRMED"
            if field == "isolation" and is_unconfirmed_status(before.isolation_status):
                nested["status"] = before.isolation_status or "UNCONFIRMED"
            pm[field] = nested
            continue
        if field in ("pass_mode", "limit_mode") and isinstance(val, dict):
            cleaned = {
                str(k): _coerce_pass_mode(v)
                for k, v in val.items()
                if _coerce_pass_mode(v)
            }
            pm[field] = cleaned
            continue
        pm[field] = val
    # Never invent IOH/IOL via the panel.
    for banned in ("voh_table", "vol_table", "ioh_a", "iol_a"):
        pm.pop(banned, None)
    data["product_model"] = pm
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return panel_payload(key)


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
    pass_mode = _pass_mode(blob, schmitt)
    if not limit_mode:
        limit_mode = dict(pass_mode)
    tt_top = str(blob.get("truth_table_status") or "").strip()
    if tt_top:
        tt_status = tt_top
    if not tt_status:
        tt_status = "UNCONFIRMED"
    iso_status = iso_status or str(blob.get("isolation_status") or "")
    if not iso_status:
        iso_status = tt_status
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
        isolation_status=iso_status,
        dc_limits=dc_limits,
        limit_mode=limit_mode,
        pass_mode=pass_mode,
        pin_drive=pin_drive,
        recipe=recipe,
        output_pin=output_pin,
        status=str(blob.get("status") or tt_status),
        vcc_list_status=str(blob.get("vcc_list_status") or ""),
        vcc_op_status=str(blob.get("vcc_op_status") or "RANGE_METADATA"),
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
