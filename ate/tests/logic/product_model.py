"""Path B Logic product-model loader (schema in YAML, not per-chip Python).

Isolation is derived from truth_table unless the part YAML supplies an
explicit isolation block. Do not branch on part name.

truth_table.status UNCONFIRMED / HOLD_CONFIRM / PROVISIONAL is not
Datasheet-signed. Runtime must not report those tables as confirmed or green.
See Lim goldens are not loaded here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import yaml

from ate.core.paths import PARTS_DIR, REPO_ROOT

# Setup Logic DC panel binds save to this schema (not an opaque key tuple).
CARD_FIELDS_SCHEMA_PATH = REPO_ROOT / "docs" / "datasheet" / "card_fields.schema.yaml"
_BANNED_PANEL_KEYS = frozenset({"voh_table", "vol_table", "ioh_a", "iol_a"})

_H = frozenset({"H", "1", "TRUE", "HIGH"})
_L = frozenset({"L", "0", "FALSE", "LOW"})
_Z = frozenset({"Z", "HZ", "HIZ", "HI-Z"})
_X = frozenset({"X", "DC", "DONTCARE", "DON'T-CARE"})

# Datasheet-signed CONFIRMED is greenable for the status gate.
# Bare CONFIRM (no ED) is not signed.
_SIGNED_STATUSES = frozenset(
    {
        "CONFIRMED",
        "DATASHEET-SIGNED",
        "DATASHEET_SIGNED",
        "DATASHEET-SIGNED CONFIRM",
        "DATASHEET_SIGNED_CONFIRM",
        "DATASHEET-SIGNED-CONFIRM",
        "DATASHEET-SIGNED CONFIRMED",
        "DATASHEET-SIGNED-CONFIRMED",
        "DATASHEET_SIGNED_CONFIRMED",
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
        "FROM-DATASHEET-FUNCTION-TABLE",
        "FROM DATASHEET FUNCTION TABLE",
    }
)
_PASS_MODES = frozenset({"range", "min_only", "max_only", "fail_open", "unspec"})


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
    if "FROM-DATASHEET" in token:
        return True
    return False


def claimed_signed_without_datasheet(status: Any) -> bool:
    """CONFIRM / SIGNED / from_datasheet without the Datasheet-signed token."""
    if is_datasheet_signed(status):
        return False
    s = _norm_status(status)
    if not s:
        return False
    token = s.replace(" ", "-")
    if s in ("CONFIRM", "SIGNED", "DATASHEET"):
        return True
    if s.startswith("CONFIRM") or s == "GREEN":
        return True
    if "FROM-DATASHEET" in token:
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
    source: str = ""  # derived_track | derived_invert | explicit


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
    gaps: list[str] = field(default_factory=list)
    wire_map: dict[str, Any] = field(default_factory=dict)
    settle_prompt: dict[str, Any] = field(default_factory=dict)
    data_paths: dict[str, Any] = field(default_factory=dict)
    vcc_grid: dict[str, Any] = field(default_factory=dict)
    sample_size: Optional[int] = None
    excel_plots: dict[str, Any] = field(default_factory=dict)
    workbook_policy: dict[str, Any] = field(default_factory=dict)
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


def _excel_plots_blob(blob: dict[str, Any]) -> dict[str, Any]:
    raw = blob.get("excel_plots")
    if isinstance(raw, list):
        return {"series": list(raw)}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _workbook_policy_blob(blob: dict[str, Any]) -> dict[str, Any]:
    """golden_auto / auto overwrite Version; pretty / ultimate_manual never auto.

    Nested workbook: {golden_auto: {policy: ...}, ultimate_manual: {note: ...}}
    from the CONFIRMED card is flattened. Do not invent a data_paths.ultimate key.
    """
    out: dict[str, Any] = {}
    raw = blob.get("workbook_policy")
    if isinstance(raw, dict):
        out.update({str(k).strip(): v for k, v in raw.items() if str(k).strip()})
    elif isinstance(raw, str) and raw.strip():
        out["golden_auto"] = raw.strip()
    wb = blob.get("workbook")
    if isinstance(wb, dict):
        ga = wb.get("golden_auto")
        if isinstance(ga, dict) and ga.get("policy"):
            out.setdefault("golden_auto", str(ga.get("policy") or "").strip())
        elif isinstance(ga, str) and ga.strip():
            out.setdefault("golden_auto", ga.strip())
        um = wb.get("ultimate_manual") or wb.get("pretty")
        if isinstance(um, dict):
            note = str(um.get("note") or um.get("policy") or "").strip().lower()
            if "never" in note or str(um.get("policy") or "").strip() == "never_auto_write":
                out.setdefault("ultimate_manual", "never_auto_write")
                out.setdefault("pretty", "never_auto_write")
        elif isinstance(um, str) and um.strip():
            out.setdefault("ultimate_manual", um.strip())
    plots = blob.get("excel_plots")
    if isinstance(plots, dict) and not out:
        nested = plots.get("policy") or plots.get("workbook_policy")
        if isinstance(nested, dict):
            out.update({str(k).strip(): v for k, v in nested.items() if str(k).strip()})
        elif nested not in (None, ""):
            out.setdefault("golden_auto", str(nested).strip())
    ga = str(out.get("golden_auto") or out.get("auto") or "").strip()
    um = str(out.get("ultimate_manual") or out.get("pretty") or "").strip()
    if ga:
        out.setdefault("golden_auto", ga)
        out.setdefault("auto", ga)
    if um:
        out.setdefault("ultimate_manual", um)
        out.setdefault("pretty", um)
    return out


def load_part_yaml(part_key: str) -> dict[str, Any]:
    key = str(part_key or "").strip().lower()
    if not key:
        return {}
    path = PARTS_DIR / f"{key}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _model_block(blob: Any) -> dict[str, Any]:
    """Accept product_model: or import-format logic_dc: (same mapping)."""
    if not isinstance(blob, dict):
        return {}
    for key in ("product_model", "logic_dc"):
        inner = blob.get(key)
        if isinstance(inner, dict) and inner:
            return dict(inner)
    if blob.get("logic_inputs") or blob.get("truth_table") or blob.get("pins"):
        return dict(blob)
    return {}


def load_product_model_dict(part_key: str) -> dict[str, Any]:
    """Return the product_model mapping, or {} if this part is not Path B.

    Adjacent file: ate/config/parts/<key>.model.yaml (optional). Inline
    `product_model:` wins over import-format `logic_dc:` on overlapping keys.
    """
    key = str(part_key or "").strip().lower()
    if not key:
        return {}
    merged: dict[str, Any] = {}
    adj = PARTS_DIR / f"{key}.model.yaml"
    if adj.is_file():
        blob = yaml.safe_load(adj.read_text(encoding="utf-8")) or {}
        inner = _model_block(blob)
        if inner:
            merged.update(inner)
        elif isinstance(blob, dict) and not any(k in blob for k in ("product_model", "logic_dc")):
            merged.update(blob)
    part = load_part_yaml(key)
    logic_dc = part.get("logic_dc")
    if isinstance(logic_dc, dict):
        merged.update(logic_dc)
    inline = part.get("product_model")
    if isinstance(inline, dict):
        merged.update(inline)
    return merged


def has_product_model(part_key: str) -> bool:
    blob = load_product_model_dict(part_key)
    return bool(blob.get("logic_inputs") or blob.get("pins") or blob.get("truth_table"))


def _raw_blob(model: Any) -> dict[str, Any]:
    if isinstance(model, dict):
        return model
    raw = getattr(model, "raw", None)
    return raw if isinstance(raw, dict) else {}


def is_open_drain(model: Any) -> bool:
    """Open-drain: VOH skip. Y=Z is output OFF, not OE-gated IOZ. No part-name ifs."""
    raw = _raw_blob(model)
    ot = str(raw.get("output_type") or raw.get("output_kind") or "").strip().lower()
    ot = ot.replace("-", "_").replace(" ", "_")
    return ot in ("open_drain", "opendrain", "od")


def is_sequential(model: Any) -> bool:
    """Shift-register / sequential: not combinational 2^n gate ICC. No part-name ifs."""
    raw = _raw_blob(model)
    pc = str(raw.get("product_class") or "").strip().lower().replace("-", "_")
    recipe = getattr(model, "recipe", None)
    if not isinstance(recipe, dict):
        recipe = raw.get("recipe") if isinstance(raw.get("recipe"), dict) else {}
    runner = str((recipe or {}).get("runner") or "").strip().lower().replace("-", "_")
    if "sequential" in pc or "shift_register" in pc:
        return True
    if runner.startswith("sequential") or "shift_register" in runner:
        return True
    return False


def _recipe_blob(model: Any) -> dict[str, Any]:
    recipe = getattr(model, "recipe", None)
    if isinstance(recipe, dict):
        return recipe
    raw = _raw_blob(model)
    rec = raw.get("recipe")
    return rec if isinstance(rec, dict) else {}


def dual_channel_continue(model: Any) -> bool:
    """recipe.dual_channel_continue: CHA then CHB with operator Continue.

    Reuses the OpAmp dual Continue pattern as DATA. Default false (1Gxx CHA-only).
    Do not invent a 2G part YAML without a Datasheet card.
    """
    raw = _recipe_blob(model).get("dual_channel_continue")
    if raw is True:
        return True
    if raw is False or raw is None or raw == "":
        return False
    s = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    return s in ("true", "yes", "1", "on", "cha_then_chb", "dual")


def recipe_channels(model: Any) -> list[str]:
    """recipe.channels DATA (CHA / CHB). Empty unless listed or dual_channel_continue."""
    raw = _recipe_blob(model).get("channels")
    order = ("CHA", "CHB")
    picked: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            s = str(item).strip().upper().replace("CHANNEL", "CH").replace(" ", "")
            if s in ("A", "CHA", "CH1"):
                picked.append("CHA")
            elif s in ("B", "CHB", "CH2"):
                picked.append("CHB")
    out = [c for c in order if c in picked]
    if out:
        return out
    if dual_channel_continue(model):
        return ["CHA", "CHB"]
    return []


def apply_dual_channel_continue(specs: list[Any], model: Any) -> list[Any]:
    """OR recipe.dual_channel_continue onto Path B specs at run. Do not wrap TestSpec.run."""
    if not dual_channel_continue(model):
        return list(specs)
    from dataclasses import replace as _replace

    out: list[Any] = []
    for spec in specs:
        if getattr(spec, "dual_channel", True):
            out.append(spec)
            continue
        try:
            out.append(_replace(spec, dual_channel=True))
        except TypeError:
            out.append(spec)
    return out


def merge_recipe_channels(model: Any, selected: list[str] | None) -> list[str]:
    """Keep operator pick; expand CHA-only to recipe CHA then CHB when the flag is on."""
    chans = [str(c).upper() for c in (selected or []) if str(c).strip()]
    if not dual_channel_continue(model):
        return chans or ["CHA"]
    want = recipe_channels(model) or ["CHA", "CHB"]
    picked = set(chans)
    if not chans or picked <= {"CHA"} and "CHB" in want:
        return list(want)
    return chans


def ioz_force_vector(model: ProductModel) -> dict[str, str]:
    """IOZ only when OE inactive. Data don't-care. Never force OE active."""
    if not model.has_oe():
        raise RuntimeError(
            f"ioz: oe is none on {model.part} -- IOZ is not applicable. "
            "Remove ioz from enabled_tests."
        )
    vec = {model.oe_pin: model.oe_inactive_level()}
    for pin in model.logic_inputs:
        vec.setdefault(pin, "L")
    return vec


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
    """Sweep corners from vcc_grid merge, else YAML lists. Never expand vcc_op_min/max."""
    merged = merge_vcc_grid(blob.get("vcc_grid"))
    if merged:
        return merged
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
    """Unused ties so Y tracks (preferred) or inverts the swept pin.

    See Lim RS1G97 goldens are the reference algorithm: Y must follow the
    swept pin non-inverting when a combo exists. Invert is recorded only
    when no track combo exists. No part-name branches.
    """
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
                        source="derived_track",
                    )
                )
            elif y_l == "H" and y_h == "L":
                patterns.append(
                    IsolationPattern(
                        sweep_pin=sweep,
                        fix=dict(fix),
                        y_expect="invert",
                        vil_sweep="reverse",
                        source="derived_invert",
                    )
                )
        out[sweep] = patterns
    return out


def _y_expect_from_row(row: dict[str, Any], default: str = "track") -> str:
    if "y_tracks" in row:
        return "track" if bool(row.get("y_tracks")) else "invert"
    raw = str(row.get("y_expect") or row.get("expect") or row.get("polarity") or default)
    s = raw.strip().lower().replace(" ", "_")
    if s in ("track", "tracks", "noninv", "non_inverting", "follow"):
        return "track"
    if s in ("invert", "inverted", "not", "not_c", "inverting"):
        return "invert"
    return default if default in ("track", "invert") else "track"


def _fix_from_row(row: dict[str, Any]) -> dict[str, str]:
    fix_raw = row.get("hold") if isinstance(row.get("hold"), dict) else None
    if fix_raw is None:
        fix_raw = row.get("fix") if isinstance(row.get("fix"), dict) else {}
    return {str(k).strip().upper(): _norm_level(v) for k, v in fix_raw.items()}


def _pattern_from_row(row: dict[str, Any], default_pin: str, status: str = "") -> Optional[IsolationPattern]:
    if not isinstance(row, dict):
        return None
    sweep = str(row.get("sweep") or row.get("sweep_pin") or default_pin).strip().upper()
    if not sweep:
        return None
    expect = _y_expect_from_row(row)
    vil = str(row.get("vil_sweep") or "").strip().lower()
    if expect == "invert" and not vil:
        vil = "reverse"
    if not vil:
        vil = "rising_then_falling"
    return IsolationPattern(
        sweep_pin=sweep,
        fix=_fix_from_row(row),
        y_expect=expect,
        vil_sweep=vil,
        status=str(row.get("status") or status),
        source="explicit",
    )


def _parse_isolation_block(raw: Any) -> tuple[dict[str, list[IsolationPattern]], str]:
    if not isinstance(raw, dict) or not raw:
        return {}, ""
    status = str(raw.get("status") or "")
    tests = raw.get("tests") if isinstance(raw.get("tests"), dict) else raw
    out: dict[str, list[IsolationPattern]] = {}
    for key, val in tests.items() if isinstance(tests, dict) else []:
        if str(key).strip().lower() in ("status", "note", "notes", "source"):
            continue
        pin = str(key).strip().upper()
        rows = val if isinstance(val, list) else [val]
        pats: list[IsolationPattern] = []
        for row in rows:
            pat = _pattern_from_row(row, pin, status) if isinstance(row, dict) else None
            if pat:
                pats.append(pat)
        if pats:
            out[pin] = pats
    return out, status


def _parse_isolation_list(raw: Any, status: str = "") -> dict[str, list[IsolationPattern]]:
    """Product-model import shape: threshold_isolation: [{sweep, hold, y_tracks}]."""
    out: dict[str, list[IsolationPattern]] = {}
    for row in _as_list(raw):
        if not isinstance(row, dict):
            continue
        pin = str(row.get("sweep") or row.get("sweep_pin") or "").strip().upper()
        pat = _pattern_from_row(row, pin, status)
        if pat is None:
            continue
        out.setdefault(pat.sweep_pin, []).append(pat)
    return out


def apply_test_params_overlay(blob: dict[str, Any], overlay: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Version overlay from _manifest/test_params.yaml (PRD-004 keys)."""
    if not isinstance(overlay, dict) or not overlay:
        return blob
    out = dict(blob)
    overlay_set_vcc_list = False
    for key in ("vcc_list", "vcc_sweep_list", "vcc_sweep"):
        nums = _floats(overlay.get(key))
        if nums:
            out["vcc_list"] = nums
            overlay_set_vcc_list = True
            break
    if overlay.get("logic_inputs"):
        out["logic_inputs"] = overlay["logic_inputs"]
    recipe = dict(_as_dict(out.get("recipe")))
    if overlay.get("levels") is not None:
        recipe["levels"] = overlay["levels"]
    if overlay.get("rails") is not None:
        recipe["rails"] = overlay["rails"]
    nested = overlay.get("recipe")
    if isinstance(nested, dict):
        for rk, rv in nested.items():
            recipe[rk] = rv
    if "stable_eps_A" in overlay:
        recipe["stable_eps_A"] = overlay.get("stable_eps_A")
    if recipe != _as_dict(out.get("recipe")):
        out["recipe"] = recipe
    if overlay.get("oe") is not None:
        out["oe"] = overlay["oe"]
    if overlay.get("schmitt") is not None:
        out["schmitt"] = overlay["schmitt"]
    for iso_key in ("isolation", "threshold_isolation"):
        if overlay.get(iso_key) is not None:
            out[iso_key] = overlay[iso_key]
    if isinstance(overlay.get("pass_mode"), dict):
        pm = dict(_as_dict(out.get("pass_mode")))
        lm = dict(_as_dict(out.get("limit_mode")))
        for k, v in overlay["pass_mode"].items():
            pm[str(k)] = str(v)
            lm[str(k)] = str(v)
        out["pass_mode"] = pm
        out["limit_mode"] = lm
    if overlay.get("gaps") is not None:
        out["gaps"] = overlay["gaps"]
    grid_over = overlay.get("vcc_grid") if isinstance(overlay.get("vcc_grid"), dict) else None
    if grid_over is None and isinstance(overlay.get("vcc_plan"), dict):
        # vcc_plan is the user-facing alias of vcc_grid (Version overlay + panel).
        grid_over = overlay.get("vcc_plan")
    if isinstance(grid_over, dict):
        base = out.get("vcc_grid") if isinstance(out.get("vcc_grid"), dict) else {}
        merged = dict(grid_over)
        if is_datasheet_signed((base or {}).get("status")) and not is_datasheet_signed(
            merged.get("status")
        ):
            merged["status"] = base.get("status")
        out["vcc_grid"] = merged
    elif overlay_set_vcc_list:
        # Overlay vcc_list must win over YAML vcc_grid (scale SIM vcc_list: [3.3]).
        out.pop("vcc_grid", None)
    if overlay.get("sample_size") is not None:
        out["sample_size"] = overlay["sample_size"]
    return out


def _yaml_gaps(blob: dict[str, Any]) -> list[str]:
    raw = blob.get("gaps")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _merge_isolation(
    derived: dict[str, list[IsolationPattern]],
    explicit: dict[str, list[IsolationPattern]],
) -> dict[str, list[IsolationPattern]]:
    """Derived from truth_table is the algorithm. Explicit YAML overlays per pin."""
    out = {k: list(v) for k, v in derived.items()}
    for pin, pats in explicit.items():
        if pats:
            out[pin] = list(pats)
    return out


def _coerce_pass_mode(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace("-", "_")
    if s in _PASS_MODES:
        return s
    return ""


def _vcc_key(v: float) -> float:
    return round(float(v), 6)


def _grid_limit_pair(row: dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    vih = _opt_float(row.get("VIH_min_V", row.get("vih_min_v")))
    vil = _opt_float(row.get("VIL_max_V", row.get("vil_max_v")))
    return vih, vil


def _step_band(start: float, stop: float, step: float) -> list[float]:
    """Inclusive start..stop. Range steps inherit band limits -- not stored as fixed rows."""
    try:
        a = float(start)
        b = float(stop)
        s = float(step)
    except (TypeError, ValueError):
        return []
    if s <= 0:
        return []
    if b + 1e-9 < a:
        return []
    n = int(round((b - a) / s))
    if n < 0:
        return []
    out: list[float] = []
    for i in range(n + 1):
        v = _vcc_key(a + i * s)
        if v > b + 1e-8:
            break
        out.append(v)
    if out and abs(out[-1] - _vcc_key(b)) > 1e-6 and out[-1] < b:
        out.append(_vcc_key(b))
    return out


def _stimulus_token(raw: Any) -> str:
    s = str(raw or "").strip().upper().replace("-", "_").replace("/", "_").replace(" ", "_")
    if s in ("PSU_MSO", "PSUMSO"):
        return "PSU_MSO"
    if s == "AWG":
        return "AWG"
    return ""


def normalize_vcc_grid(raw: Any) -> dict[str, Any]:
    """product_model.vcc_grid. Empty mapping if absent. Do not invent VIH/VIL numbers."""
    if not isinstance(raw, dict) or not raw:
        return {}
    stim = _stimulus_token(raw.get("stimulus"))
    pm: dict[str, str] = {}
    if isinstance(raw.get("pass_mode"), dict):
        for key, val in raw["pass_mode"].items():
            mode = _coerce_pass_mode(val)
            if mode:
                pm[str(key).strip()] = mode
    pm.setdefault("VIH", "min_only")
    pm.setdefault("VIL", "max_only")
    fixed: list[dict[str, Any]] = []
    for row in _as_list(raw.get("fixed_points")):
        if not isinstance(row, dict):
            continue
        vcc = _opt_float(row.get("vcc"))
        if vcc is None:
            continue
        vih, vil = _grid_limit_pair(row)
        item: dict[str, Any] = {"vcc": _vcc_key(vcc), "VIH_min_V": vih, "VIL_max_V": vil}
        for k, val in row.items():
            key = str(k)
            if key in ("vcc", "VIH_min_V", "vih_min_v", "VIL_max_V", "vil_max_v"):
                continue
            item[key] = val
        fixed.append(item)
    ranges: list[dict[str, Any]] = []
    for row in _as_list(raw.get("ranges")):
        if not isinstance(row, dict):
            continue
        start = _opt_float(row.get("start"))
        stop = _opt_float(row.get("stop"))
        step = _opt_float(row.get("step"))
        if step is None:
            step = 0.1
        if start is None or stop is None:
            continue
        vih, vil = _grid_limit_pair(row)
        item: dict[str, Any] = {
            "start": _vcc_key(start),
            "stop": _vcc_key(stop),
            "step": float(step),
            "VIH_min_V": vih,
            "VIL_max_V": vil,
        }
        label = str(row.get("label") or "").strip()
        if label:
            item["label"] = label
        for k, val in row.items():
            key = str(k)
            if key in (
                "start",
                "stop",
                "step",
                "VIH_min_V",
                "vih_min_v",
                "VIL_max_V",
                "vil_max_v",
                "label",
            ):
                continue
            item[key] = val
        ranges.append(item)
    out: dict[str, Any] = {
        "stimulus": stim or str(raw.get("stimulus") or "").strip(),
        "pass_mode": pm,
        "fixed_points": fixed,
        "ranges": ranges,
        "status": str(raw.get("status") or "UNCONFIRMED").strip() or "UNCONFIRMED",
    }
    kind = str(raw.get("kind") or "").strip()
    if kind:
        out["kind"] = kind
    return out


def vcc_grid_owned(grid: Any) -> dict[float, dict[str, Any]]:
    """Range steps first; exact-VCC fixed_points overwrite ownership."""
    g = normalize_vcc_grid(grid)
    owned: dict[float, dict[str, Any]] = {}
    for band in g.get("ranges") or []:
        rec_base = {
            "VIH_min_V": band.get("VIH_min_V"),
            "VIL_max_V": band.get("VIL_max_V"),
            "source": "range",
        }
        label = band.get("label")
        if label:
            rec_base["label"] = label
        for v in _step_band(band["start"], band["stop"], band["step"]):
            item = dict(rec_base)
            item["vcc"] = v
            owned[_vcc_key(v)] = item
    for pt in g.get("fixed_points") or []:
        v = _vcc_key(pt["vcc"])
        owned[v] = {
            "vcc": v,
            "VIH_min_V": pt.get("VIH_min_V"),
            "VIL_max_V": pt.get("VIL_max_V"),
            "source": "fixed",
        }
    return owned


def merge_vcc_grid(grid: Any) -> list[float]:
    """Unique merged vcc_list (fixed + range steps). Range steps are not fixed-point rows."""
    owned = vcc_grid_owned(grid)
    return [owned[k]["vcc"] for k in sorted(owned)]


def lookup_vcc_grid_limits(model: Any, vcc: Any) -> Optional[dict[str, Any]]:
    """Per-VCC VIH_min_V / VIL_max_V from owning fixed point or range band."""
    grid = getattr(model, "vcc_grid", None)
    if grid is None and isinstance(model, dict):
        grid = model.get("vcc_grid", model)
    try:
        key = _vcc_key(float(vcc))
    except (TypeError, ValueError):
        return None
    return vcc_grid_owned(grid).get(key)


def vcc_grid_stimulus(model: Any) -> str:
    """PSU_MSO | AWG. Missing grid defaults AWG when any pin_drive is awg (97/126)."""
    grid: Any = getattr(model, "vcc_grid", None)
    if isinstance(model, dict):
        grid = model.get("vcc_grid") if isinstance(model.get("vcc_grid"), dict) else model
    token = _stimulus_token((grid or {}).get("stimulus") if isinstance(grid, dict) else "")
    if token:
        return token
    drives = getattr(model, "pin_drive", None) or {}
    if isinstance(model, dict) and not drives:
        drives = model.get("pin_drive") or {}
    for dm in drives.values() if isinstance(drives, dict) else []:
        src = getattr(dm, "src", None) or (dm.get("src") if isinstance(dm, dict) else "")
        if str(src or "").strip().lower() == "awg":
            return "AWG"
    return "AWG"


def vcc_grid_unconfirmed(model: Any) -> bool:
    """Numbers on vcc_grid are not greenable until Datasheet-signed CONFIRMED."""
    grid = getattr(model, "vcc_grid", None)
    if isinstance(model, dict):
        grid = model.get("vcc_grid")
    if not isinstance(grid, dict) or not grid:
        return False
    if grid.get("fixed_points") in (None, []) and grid.get("ranges") in (None, []) and not grid.get("status"):
        return False
    # Do not inherit product_model.status CONFIRMED -- vcc_grid.status is its own numbers gate.
    st = grid.get("status") or "UNCONFIRMED"
    if is_datasheet_signed(st):
        return False
    return True


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
        out.setdefault("HYST", "range")
    else:
        # Drop a collapsed input_threshold:range so callers must use VIH/VIL.
        if "VIH" not in out and "VIH_V" not in out:
            out.setdefault("VIH", "min_only")
        if "VIL" not in out and "VIL_V" not in out:
            out.setdefault("VIL", "max_only")
    grid = blob.get("vcc_grid") if isinstance(blob.get("vcc_grid"), dict) else {}
    if isinstance(grid.get("pass_mode"), dict):
        for key, val in grid["pass_mode"].items():
            mode = _coerce_pass_mode(val)
            if mode:
                out[str(key).strip()] = mode
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
        keys.extend(["VT+", "VTPLUS", "VTPLUS_V", "vth_vt_plus", "input_threshold", "vth"])
    if mid.upper() in ("VTMINUS_V", "VT-", "VTMINUS"):
        keys.extend(["VT-", "VTMINUS", "VTMINUS_V", "vth_vt_minus", "input_threshold", "vth"])
    if "HYST" in mid.upper() or "HYSTERESIS" in mid.upper():
        keys.extend(["HYST", "hyst", "hysteresis"])
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
    if model.vcc_grid:
        gst = str((model.vcc_grid or {}).get("status") or "")
        if vcc_grid_unconfirmed(model):
            gaps.append(
                f"vcc_grid.status={gst or 'UNCONFIRMED'} "
                "(numbers not Datasheet-signed; not greenable)"
            )
        gaps.append(
            f"stimulus={vcc_grid_stimulus(model)}; "
            "range steps inherit band VIH/VIL (not a fixed-point row)"
        )
    for name, block in (model.dc_limits or {}).items():
        if isinstance(block, dict) and is_unconfirmed_status(block.get("status")):
            gaps.append(f"{name}: {block.get('status')} ({block.get('note') or 'no invented loads'})")
    if not model.has_oe():
        gaps.append("oe=none: IOZ not applicable (do not enable ioz/ioff)")
    for g in model.gaps:
        if g not in gaps:
            gaps.append(g)
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
    ui = model_to_ui(model)
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
        "vcc_grid": dict(model.vcc_grid or {}),
        "vcc_plan": dict(model.vcc_grid or {}),
        "vcc_grid_preview": list(model.vcc_list),
        "stimulus": vcc_grid_stimulus(model),
        "sample_size": model.sample_size,
        "pass_mode": dict(model.pass_mode),
        "limit_mode": dict(model.limit_mode),
        "truth_table": tt,
        "isolation": iso,
        "isolation_run": ui.get("isolation"),
        "threshold_isolation": ui.get("threshold_isolation"),
        "icc_corners": ui.get("icc_corners"),
        "icc_pins": ui.get("icc_pins"),
        "logic_inputs": list(model.logic_inputs),
        "gaps": model_gaps(model),
        "pins": [{"name": p.name, "role": p.role, "number": p.number} for p in model.pins],
        "recipe": dict(model.recipe),
        "pin_drive": {
            name: {"src": dm.src, "ch": dm.ch} for name, dm in model.pin_drive.items()
        },
        "dc_limits": dict(model.dc_limits),
        "is_open_drain": is_open_drain(model),
        "is_sequential": is_sequential(model),
        "dual_channel_continue": dual_channel_continue(model),
        "recipe_channels": recipe_channels(model),
        "pin_wiring_labels": format_pin_wiring_labels(model),
        "wire_map": dict(model.wire_map),
        "settle_prompt": dict(model.settle_prompt),
        "data_paths": dict(model.data_paths),
        "excel_plots": dict(model.excel_plots or {}),
        "workbook_policy": model.workbook_policy,
        "card_fields": card_fields_for_panel(blob, model),
        "oop_schema": CARD_FIELDS_SCHEMA_PATH.name,
    }


def load_card_fields_schema() -> dict[str, Any]:
    """OOP_SCHEMA / card_fields. Missing file is FAIL-closed (no opaque fallback)."""
    if not CARD_FIELDS_SCHEMA_PATH.is_file():
        raise RuntimeError(
            f"card_fields schema missing: {CARD_FIELDS_SCHEMA_PATH}. "
            "Panel save cannot invent keys."
        )
    data = yaml.safe_load(CARD_FIELDS_SCHEMA_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("fields"), list):
        raise RuntimeError("card_fields.schema.yaml must be a mapping with fields: []")
    return data


def card_field_specs() -> list[dict[str, Any]]:
    schema = load_card_fields_schema()
    out: list[dict[str, Any]] = []
    for row in schema.get("fields") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        if not key or key in _BANNED_PANEL_KEYS:
            continue
        out.append(dict(row))
    return out


def panel_save_keys() -> tuple[str, ...]:
    """Editable product_model keys from card_fields.schema.yaml (not a hardcoded tuple)."""
    keys: list[str] = []
    for row in card_field_specs():
        if row.get("editable", True) is False:
            continue
        key = str(row.get("key") or "")
        if key:
            keys.append(key)
    return tuple(keys)


def _schema_field(key: str) -> dict[str, Any]:
    for row in card_field_specs():
        if row.get("key") == key:
            return row
    return {}


def _lookup_card_value(blob: dict[str, Any], model: ProductModel, key: str) -> Any:
    if key.startswith("recipe."):
        rk = key.split(".", 1)[1]
        rec = blob.get("recipe") if isinstance(blob.get("recipe"), dict) else {}
        if rk in rec:
            return rec.get(rk)
        return (model.recipe or {}).get(rk)
    if key in blob:
        return blob.get(key)
    attr_map = {
        "part": model.part,
        "status": model.status,
        "pins": [{"name": p.name, "role": p.role, "number": p.number} for p in model.pins],
        "logic_inputs": list(model.logic_inputs),
        "output_pin": model.output_pin,
        "oe": blob.get("oe", model.oe_mode),
        "schmitt": model.schmitt,
        "truth_table": blob.get("truth_table"),
        "truth_table_status": model.truth_table_status,
        "isolation": blob.get("isolation"),
        "isolation_status": model.isolation_status,
        "pass_mode": dict(model.pass_mode),
        "limit_mode": dict(model.limit_mode),
        "vcc_list": list(model.vcc_list),
        "vcc_sweep_list": list(model.vcc_list),
        "vcc_list_status": model.vcc_list_status,
        "vcc_op_min": model.vcc_op_min,
        "vcc_op_max": model.vcc_op_max,
        "vcc_op_status": model.vcc_op_status,
        "vcc_grid": dict(model.vcc_grid or {}),
        "vcc_plan": dict(model.vcc_grid or {}),
        "sample_size": model.sample_size,
        "recipe": dict(model.recipe),
        "gaps": list(model.gaps),
        "dc_limits": dict(model.dc_limits),
        "pin_drive": {
            name: {"src": dm.src, "ch": dm.ch} for name, dm in model.pin_drive.items()
        },
        "wire_map": dict(model.wire_map),
        "settle_prompt": dict(model.settle_prompt),
        "data_paths": dict(model.data_paths),
        "excel_plots": dict(model.excel_plots or {}),
        "workbook_policy": model.workbook_policy,
    }
    return attr_map.get(key)


def card_fields_for_panel(blob: dict[str, Any], model: ProductModel) -> list[dict[str, Any]]:
    """Per-field panel payload: assign / edit / delete. Values from product_model YAML."""
    out: list[dict[str, Any]] = []
    for spec in card_field_specs():
        row = dict(spec)
        row["value"] = _lookup_card_value(blob, model, str(spec.get("key") or ""))
        out.append(row)
    return out


def _set_pm_key(pm: dict[str, Any], key: str, val: Any) -> None:
    if "." in key:
        top, rest = key.split(".", 1)
        nested = dict(pm.get(top) if isinstance(pm.get(top), dict) else {})
        nested[rest] = val
        pm[top] = nested
        return
    pm[key] = val


def _delete_pm_key(pm: dict[str, Any], key: str) -> None:
    if "." in key:
        top, rest = key.split(".", 1)
        nested = dict(pm.get(top) if isinstance(pm.get(top), dict) else {})
        nested[rest] = None
        pm[top] = nested
        return
    if key in ("truth_table_status", "isolation_status"):
        pm[key] = "UNCONFIRMED"
        return
    if key in ("gaps", "logic_inputs"):
        pm[key] = []
        return
    if key in ("vcc_list", "vcc_sweep_list"):
        return
    pm[key] = None


def save_product_model_fields(part_key: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Write editable Path B fields back to part YAML. Cannot promote to Datasheet-signed.

    Keys come from docs/datasheet/card_fields.schema.yaml (OOP_SCHEMA). Banned
    load tables are never written. Each card field is individually settable or
    deletable (null / deleted_fields).
    """
    key = str(part_key or "").strip().lower()
    path = PARTS_DIR / f"{key}.yaml"
    if not path.is_file():
        raise RuntimeError(f"part yaml missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"part yaml is not a mapping: {path}")
    save_key = "product_model" if isinstance(data.get("product_model"), dict) else "logic_dc"
    pm = data.get(save_key)
    if not isinstance(pm, dict):
        raise RuntimeError(f"{key}: no product_model / logic_dc block to edit")
    before = load_product_model(key)
    if before is None:
        raise RuntimeError(f"{key}: product_model failed to load")
    if not isinstance(patch, dict):
        raise RuntimeError("save_product_model: patch must be a mapping")
    allowed = set(panel_save_keys())
    deleted = [str(x) for x in (patch.get("deleted_fields") or []) if str(x) in allowed]
    pending: list[str] = []
    for field in panel_save_keys():
        if field in patch or field in deleted:
            pending.append(field)
    for field in pending:
        spec = _schema_field(field)
        if field in deleted or (field in patch and patch[field] is None and spec.get("deletable", True)):
            if spec.get("deletable", True) is False:
                continue
            _delete_pm_key(pm, field)
            continue
        if field not in patch:
            continue
        val = patch[field]
        if field in ("vcc_list", "vcc_sweep_list"):
            nums = _floats(val) if not isinstance(val, (int, float)) else [float(val)]
            if not nums:
                continue
            pm["vcc_list"] = nums
            pm["vcc_sweep_list"] = nums
            continue
        if field in ("truth_table_status", "isolation_status"):
            if is_datasheet_signed(val) and not is_datasheet_signed(
                before.truth_table_status if field == "truth_table_status" else before.isolation_status
            ):
                raise RuntimeError(
                    "Panel cannot promote status to Datasheet-signed. "
                    "Hand-edit YAML after a signed datasheet confirm."
                )
            if val in (None, ""):
                val = "UNCONFIRMED"
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
        if field == "recipe" and isinstance(val, dict):
            rec = dict(pm.get("recipe") if isinstance(pm.get("recipe"), dict) else {})
            rec.update(val)
            if "stable_eps_A" not in rec:
                rec["stable_eps_A"] = None
            pm["recipe"] = rec
            continue
        if field == "vcc_plan":
            # Alias: store as vcc_grid. vcc_grid in the same patch wins after.
            if isinstance(val, dict):
                pm["vcc_grid"] = val
            continue
        _set_pm_key(pm, field, val)
    for banned in _BANNED_PANEL_KEYS:
        pm.pop(banned, None)
        rec = pm.get("recipe")
        if isinstance(rec, dict):
            rec.pop(banned, None)
    data[save_key] = pm
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
    stim = ""
    grid = blob.get("vcc_grid")
    if isinstance(grid, dict):
        stim = _stimulus_token(grid.get("stimulus"))
    if stim == "PSU_MSO":
        # CH1 is VCC. CH2 reserved for Y-load when voh/vol tables exist.
        # Default leftover inputs at CH3+ (do not steal CH2 for an input).
        psu_ch = 3
        for name in names:
            if name in out:
                continue
            if psu_ch == 2:
                psu_ch = 3
            out[name] = DriveMap(src="psu", ch=psu_ch)
            psu_ch += 1
        return out
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


def load_product_model(
    part_key: str,
    overlay: Optional[dict[str, Any]] = None,
) -> Optional[ProductModel]:
    """Load Path B model. overlay is campaign _manifest/test_params.yaml (optional)."""
    key = str(part_key or "").strip().lower()
    blob = load_product_model_dict(key)
    if not blob:
        return None
    blob = apply_test_params_overlay(blob, overlay)
    part_yaml = load_part_yaml(key)
    pins = _pins(blob)
    logic_inputs = _logic_inputs(blob, pins)
    if not logic_inputs and not pins:
        return None
    oe_mode, oe_pin = _oe(blob, pins)
    schmitt = bool(blob.get("schmitt"))
    vcc_list = _vcc_list(blob, part_yaml)
    vcc_grid = normalize_vcc_grid(blob.get("vcc_grid"))
    sample_size = None
    try:
        if blob.get("sample_size") is not None:
            sample_size = max(1, int(blob.get("sample_size")))
        elif part_yaml.get("sample_size") is not None:
            sample_size = max(1, int(part_yaml.get("sample_size")))
    except (TypeError, ValueError):
        sample_size = None
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
    listed = _parse_isolation_list(blob.get("threshold_isolation"), iso_status)
    for pin, pats in listed.items():
        if pin not in explicit and pats:
            explicit[pin] = pats
        elif pin in explicit and pats:
            # Import-format rows overlay the same pin when YAML listed both.
            have = {(tuple(sorted(p.fix.items())), p.y_expect) for p in explicit[pin]}
            for pat in pats:
                sig = (tuple(sorted(pat.fix.items())), pat.y_expect)
                if sig not in have:
                    explicit[pin].append(pat)
    derived = derive_isolation(
        logic_inputs=logic_inputs,
        truth_table=truth_table,
        output_pin=output_pin,
        oe_pin=oe_pin if oe_mode != "none" else "",
        oe_active=oe_active_level(oe_mode) if oe_mode != "none" else "",
    )
    isolation = _merge_isolation(derived, explicit)
    dc_limits = _as_dict(blob.get("dc_limits"))
    limit_mode_raw = blob.get("limit_mode")
    limit_mode = (
        {str(k): str(v) for k, v in limit_mode_raw.items()}
        if isinstance(limit_mode_raw, dict)
        else {}
    )
    recipe = _as_dict(blob.get("recipe"))
    recipe.setdefault("settle_s", 0.05)
    recipe.setdefault("stable_n", 3)
    recipe.setdefault("stable_eps_V", 0.005)
    recipe.setdefault("settle_timeout_s", 2.0)
    # current settle eps: default null (FAIL-closed). Do not invent a uA/amp number.
    if "stable_eps_A" not in recipe:
        recipe["stable_eps_A"] = None
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
        vcc_list_status=str(blob.get("vcc_list_status") or (vcc_grid.get("status") if vcc_grid else "") or ""),
        vcc_op_status=str(blob.get("vcc_op_status") or "RANGE_METADATA"),
        gaps=_yaml_gaps(blob),
        wire_map=_as_dict(blob.get("wire_map")),
        settle_prompt=_as_dict(blob.get("settle_prompt")),
        data_paths=_as_dict(blob.get("data_paths")),
        vcc_grid=vcc_grid,
        sample_size=sample_size,
        excel_plots=_excel_plots_blob(blob),
        workbook_policy=_workbook_policy_blob(blob),
        raw=blob,
    )


def logic_volts(level: Any, vcc: float) -> float:
    lv = _norm_level(level)
    if lv == "H":
        return float(vcc)
    return 0.0


def icc_pins(model: ProductModel) -> list[str]:
    """Data pins, plus OE when present (ICC over data x OE space).

    Sequential shift registers are not combinational 2^n -- empty pin list.
    """
    if is_sequential(model):
        return []
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


def _skip_isolation_status(status: str) -> bool:
    """Skip PROPOSED / HOLD CONFIRM rows so a MUX guess cannot silently run."""
    s = str(status or "").strip().upper().replace("_", " ").replace("-", " ")
    if not s:
        return False
    tokens = set(s.split())
    if "PROPOSED" in tokens:
        return True
    if "HOLD" in tokens and "CONFIRM" in tokens:
        return True
    if s in ("HOLD", "HOLD CONFIRM"):
        return True
    return False


def isolation_for_run(model: ProductModel, sweep_pin: str) -> list[IsolationPattern]:
    """One combo per pin: first non-inverting track, else first invert.

    Skips PROPOSED / HOLD CONFIRM rows. CONFIRMED track rows run.
    UNCONFIRMED table status is not skipped here -- check_logic_dc
    fail-closes until Datasheet-signed CONFIRMED.
    """
    pats = [p for p in isolation_for(model, sweep_pin) if not _skip_isolation_status(p.status)]
    tracks = [p for p in pats if p.y_expect == "track"]
    if tracks:
        return [tracks[0]]
    inverts = [p for p in pats if p.y_expect == "invert"]
    if inverts:
        return [inverts[0]]
    return []


def sim_icc_plan(model: ProductModel) -> dict[str, Any]:
    if is_sequential(model):
        return {
            "pins": [],
            "n": 0,
            "corners": [],
            "note": "sequential_shift_register not combinational 2^n",
        }
    pins = icc_pins(model)
    corners = iter_logic_corners(pins)
    return {"pins": pins, "n": len(corners), "corners": corners}


def _pat_ui(pat: IsolationPattern) -> dict[str, Any]:
    return {
        "sweep": pat.sweep_pin,
        "sweep_pin": pat.sweep_pin,
        "hold": dict(pat.fix),
        "fix": dict(pat.fix),
        "y_tracks": pat.y_expect == "track",
        "y_expect": pat.y_expect,
        "vil_sweep": pat.vil_sweep,
        "status": pat.status,
        "source": pat.source,
    }


def model_to_ui(model: ProductModel) -> dict[str, Any]:
    """Panel payload: recipe + derived corners. Not a second runner."""
    plan = sim_icc_plan(model)
    iso: dict[str, Any] = {}
    threshold_isolation: list[dict[str, Any]] = []
    for pin in model.logic_inputs:
        run = isolation_for_run(model, pin)
        all_p = isolation_for(model, pin)
        iso[pin] = {"run": [_pat_ui(p) for p in run], "all": [_pat_ui(p) for p in all_p]}
        threshold_isolation.extend(_pat_ui(p) for p in run)
    oe: Any = None
    if model.has_oe():
        oe = {"pin": model.oe_pin, "active": model.oe_mode}
    return {
        "part": model.part,
        "logic_inputs": list(model.logic_inputs),
        "oe": oe,
        "schmitt": bool(model.schmitt),
        "vcc_list": list(model.vcc_list),
        "vcc_sweep_list": list(model.vcc_list),
        "vcc_grid": dict(model.vcc_grid or {}),
        "vcc_plan": dict(model.vcc_grid or {}),
        "vcc_grid_preview": list(model.vcc_list),
        "stimulus": vcc_grid_stimulus(model),
        "sample_size": model.sample_size,
        "truth_table": [dict(r) for r in model.truth_table],
        "truth_table_status": model.truth_table_status,
        "threshold_isolation": threshold_isolation,
        "isolation": iso,
        "isolation_status": model.isolation_status,
        "icc_pins": list(plan["pins"]),
        "icc_corners": int(plan["n"]),
        "icc_corner_rows": [dict(r) for r in (plan.get("corners") or [])[:16]],
        "gaps": list(model_gaps(model)),
        "has_oe": model.has_oe(),
        "limit_mode": dict(model.limit_mode),
        "pass_mode": dict(model.pass_mode),
        "levels": model.recipe.get("levels"),
        "rails": model.recipe.get("rails"),
        "settle_s": model.recipe.get("settle_s"),
        "stable_n": model.recipe.get("stable_n"),
        "stable_eps_V": model.recipe.get("stable_eps_V"),
        "stable_eps_A": model.recipe.get("stable_eps_A"),
        "settle_timeout_s": model.recipe.get("settle_timeout_s"),
        "status": model.status,
        "output_pin": model.output_pin,
        "recipe": dict(model.recipe),
        "pins": [{"name": p.name, "role": p.role, "number": p.number} for p in model.pins],
        "pin_drive": {
            name: {"src": dm.src, "ch": dm.ch} for name, dm in model.pin_drive.items()
        },
        "dc_limits": dict(model.dc_limits),
        "is_open_drain": is_open_drain(model),
        "is_sequential": is_sequential(model),
        "dual_channel_continue": dual_channel_continue(model),
        "recipe_channels": recipe_channels(model),
        "pin_wiring_labels": format_pin_wiring_labels(model),
        "wire_map": dict(model.wire_map),
        "settle_prompt": dict(model.settle_prompt),
        "data_paths": dict(model.data_paths),
        "excel_plots": dict(model.excel_plots or {}),
        "workbook_policy": model.workbook_policy,
        "card_fields": card_fields_for_panel(model.raw if isinstance(model.raw, dict) else {}, model),
        "oop_schema": CARD_FIELDS_SCHEMA_PATH.name,
    }


# AE/FAE no-code handoff. Folder templates only -- never invent nets or Excel cells.
DATA_PATH_REQUIRED = ("excel", "report", "datalog", "records")
DATA_PATH_TEMPLATES = {
    "excel": "#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/workbook/",
    "report": "sessions/report.json",
    "datalog": "sessions/datalog.md",
    "csv": "sessions/csv/",
    "report_pdf": "report.pdf",
    "records": "{test}/DUT_n/records/",
    "attach": "{test}/DUT_n/",
}
_CURRENT_HANDOFF_IDS = frozenset({"icc", "delta_icc", "ii", "ioz"})
_VOLTAGE_HANDOFF_IDS = frozenset({"input_threshold", "vth", "voh", "vol"})
_AC_HANDOFF_IDS = frozenset({"tp", "ten", "tdis"})


def known_pin_names(model: ProductModel) -> set[str]:
    return {str(p.name).strip().upper() for p in model.pins if str(p.name).strip()}


def _wire_tests(model: ProductModel) -> dict[str, Any]:
    wm = model.wire_map if isinstance(model.wire_map, dict) else {}
    tests = wm.get("tests")
    return tests if isinstance(tests, dict) else {}


def wire_map_has_test(model: ProductModel, test_id: str) -> bool:
    tid = str(test_id or "").strip().lower()
    for key in _wire_tests(model):
        if str(key).strip().lower() == tid:
            return True
    return False


def _wire_block_nonempty(block: Any) -> bool:
    if not isinstance(block, dict) or not block:
        return False
    for key in ("psu", "awg", "dmm", "scope", "gnd"):
        val = block.get(key)
        if val not in (None, "", [], {}):
            return True
    return False


def wire_map_for_test(model: ProductModel, test_id: str) -> dict[str, Any]:
    """Per-test wire map. Empty is FAIL-closed -- never invent nets."""
    tid = str(test_id or "").strip().lower()
    block: Any = None
    for key, val in _wire_tests(model).items():
        if str(key).strip().lower() == tid:
            block = val
            break
    if not _wire_block_nonempty(block):
        raise RuntimeError(
            f"{tid}: empty wire_map (CONFIRMED pins + pin_drive only; do not invent nets)"
        )
    return dict(block)


def missing_data_path_keys(model: ProductModel) -> list[str]:
    raw = model.data_paths if isinstance(model.data_paths, dict) else {}
    missing: list[str] = []
    for key in DATA_PATH_REQUIRED:
        val = raw.get(key)
        if val is None or str(val).strip() == "":
            missing.append(key)
    return missing


def _stable_eps_a_null(model: ProductModel) -> bool:
    raw = (model.recipe or {}).get("stable_eps_A")
    if raw is None:
        return True
    if isinstance(raw, str) and raw.strip().lower() in ("", "null", "none", "~", "nan"):
        return True
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return True
    if v != v:
        return True
    return v <= 0


def _campaign_tokens(test_id: str = "", dut_index: Any = None) -> dict[str, str]:
    tokens = {
        "Component": "{Component}",
        "Part": "{Part}",
        "Package": "{Package}",
        "Operator": "{Operator}",
        "Version_N": "{Version_N}",
        "test": str(test_id or "{test}") or "{test}",
        "n": "n",
    }
    try:
        from ate.core.database import get_context

        ident = get_context().identity()
    except Exception:
        ident = {}
    if isinstance(ident, dict):
        if ident.get("component"):
            tokens["Component"] = str(ident["component"])
        if ident.get("part"):
            tokens["Part"] = str(ident["part"])
        if ident.get("package"):
            tokens["Package"] = str(ident["package"])
        if ident.get("operator"):
            tokens["Operator"] = str(ident["operator"])
        if ident.get("version"):
            tokens["Version_N"] = str(ident["version"])
    if dut_index not in (None, ""):
        tokens["n"] = str(dut_index)
    return tokens


def resolve_data_paths(
    model: ProductModel,
    test_id: str = "",
    dut_index: Any = None,
) -> dict[str, str]:
    """Fill folder templates. Never invent Excel cells."""
    raw = dict(DATA_PATH_TEMPLATES)
    if isinstance(model.data_paths, dict):
        for key, val in model.data_paths.items():
            if val is not None and str(val).strip() != "":
                raw[str(key)] = val
    tokens = _campaign_tokens(test_id, dut_index)
    out: dict[str, str] = {}
    dut_token = f"DUT_{tokens['n']}"
    for key, tmpl in raw.items():
        s = str(tmpl)
        for name, val in tokens.items():
            s = s.replace("{" + name + "}", val)
        if tokens["n"] != "n":
            s = s.replace("DUT_n", dut_token)
        out[str(key)] = s
    return out


def attach_path_line(model: ProductModel, test_id: str, dut_index: Any = None) -> str:
    paths = resolve_data_paths(model, test_id, dut_index)
    return str(paths.get("attach") or paths.get("records") or "{test}/DUT_n/")


def _fmt_pin_spec(spec: Any) -> str:
    if isinstance(spec, dict):
        pin = str(spec.get("pin") or "").strip().upper()
        bits = [f"pin {pin}" if pin else "pin ?"]
        if spec.get("number") not in (None, ""):
            bits.append(f"pkg {spec.get('number')}")
        if spec.get("role"):
            bits.append(str(spec.get("role")))
        if spec.get("use"):
            bits.append(f"use {spec.get('use')}")
        return ", ".join(bits)
    text = str(spec or "").strip()
    return f"pin {text.upper()}" if text else "pin ?"


def _ch_lookup(block: dict[str, Any], ch: Any) -> Any:
    if not isinstance(block, dict):
        return None
    key = str(ch or "").strip()
    if key in block:
        return block[key]
    up = key.upper()
    for k, val in block.items():
        if str(k).strip().upper() == up:
            return val
    return None


def format_pin_wiring_labels(model: ProductModel) -> list[str]:
    """Panel pin/wiring labels from CONFIRMED pins + pin_drive. Never invent nets."""
    lines: list[str] = []
    for p in model.pins:
        bit = f"{p.name} pin {p.number} {p.role}"
        dm = (model.pin_drive or {}).get(p.name)
        if dm is not None:
            src = str(getattr(dm, "src", "") or "").strip().upper()
            ch = getattr(dm, "ch", None)
            if src and ch is not None:
                bit += f" <- {src} CH{ch}"
        lines.append(bit)
    if model.has_oe():
        lines.append(
            f"OE {model.oe_pin} active-{model.oe_mode} "
            f"(IOZ when inactive {model.oe_inactive_level()})"
        )
    if is_open_drain(model):
        lines.append("open-drain: VOH N/A skip")
    if is_sequential(model):
        lines.append("sequential: gate 2^n / ICC / dICC stay disabled")
    wm = model.wire_map if isinstance(model.wire_map, dict) else {}
    if wm:
        lines.append("wire_map present (CONFIRMED pins + pin_drive only)")
    else:
        lines.append("wire_map empty -- labels from pins + pin_drive; do not invent nets")
    return lines


def format_wire_lines(model: ProductModel, test_id: str) -> list[str]:
    """PSU CH->pin, AWG CH->input, DMM->VCC or Y, SCOPE CH->Y/debug."""
    wm = model.wire_map if isinstance(model.wire_map, dict) else {}
    block = wire_map_for_test(model, test_id)
    lines = [
        "Wire map (CONFIRMED pins + pin_drive only; do not invent nets)",
    ]
    psu = wm.get("psu") if isinstance(wm.get("psu"), dict) else {}
    awg = wm.get("awg") if isinstance(wm.get("awg"), dict) else {}
    for ch in _as_list(block.get("psu")):
        spec = _ch_lookup(psu, ch)
        lines.append(f"PSU {ch} -> {_fmt_pin_spec(spec)}")
    for ch in _as_list(block.get("awg")):
        spec = _ch_lookup(awg, ch)
        lines.append(f"AWG {ch} -> {_fmt_pin_spec(spec)}")
    gnd = wm.get("gnd")
    if gnd:
        lines.append(f"GND -> {_fmt_pin_spec(gnd)}")
    dmm = block.get("dmm")
    if isinstance(dmm, list):
        pins = ", ".join(str(x).strip().upper() for x in dmm if str(x).strip())
        lines.append(f"DMM -> {pins}")
    elif dmm not in (None, ""):
        lines.append(f"DMM -> {str(dmm).strip().upper()}")
    scope = block.get("scope") if isinstance(block.get("scope"), dict) else {}
    for ch, spec in scope.items():
        lines.append(f"SCOPE {ch} -> {_fmt_pin_spec(spec)}")
    lines.append("Human Continue after verify.")
    return lines


def format_stimulus_lines(model: ProductModel, test_id: str) -> list[str]:
    tid = str(test_id or "").strip().lower()
    drive = {
        name: f"{dm.src.upper()} CH{dm.ch}" for name, dm in (model.pin_drive or {}).items()
    }
    lines = [
        f"Stimulus: {vcc_grid_stimulus(model)} Vcc={list(model.vcc_list)}",
        f"force pin_drive={drive}",
    ]
    if tid == "voh":
        lines.append("truth_table vector: force Y=H (OE active if present)")
    elif tid == "vol":
        lines.append("truth_table vector: force Y=L (OE active if present)")
    elif tid in ("input_threshold", "vth"):
        lines.append("truth_table vector: isolation unused ties (Y tracks/invert)")
    elif tid in ("icc", "delta_icc"):
        lines.append("force: 2^n logic corners on ICC pins")
    elif tid == "ii":
        lines.append("force: swept input VI=0 and VI=max; others at rail")
    elif tid == "ioz":
        lines.append(
            f"force: {model.oe_pin}={model.oe_inactive_level()} (data don't-care)"
        )
    elif tid in _AC_HANDOFF_IDS:
        lines.append("AC wrap: Vcc from params; MSO on output_pin Y")
    return lines


def format_settle_lines(model: ProductModel, test_id: str) -> list[str]:
    sp = model.settle_prompt if isinstance(model.settle_prompt, dict) else {}
    wait = sp.get("wait", True)
    voltage = str(
        sp.get("voltage")
        or "V eps/N: wait settle_s then stable_n within stable_eps_V; timeout hard-FAIL"
    )
    current_null = str(
        sp.get("current_null")
        or "I NON_TIGHT: wait settle_s once then measure (stable_eps_A null; not greenable as tight-settle)"
    )
    current_tight = str(
        sp.get("current_tight")
        or "I tight: wait settle_s then stable_n within stable_eps_A; timeout hard-FAIL"
    )
    tid = str(test_id or "").strip().lower()
    lines = [f"Settle (show wait): wait={wait}"]
    if tid in _CURRENT_HANDOFF_IDS:
        lines.append(current_null if _stable_eps_a_null(model) else current_tight)
    elif tid in _AC_HANDOFF_IDS:
        lines.append("AC wrap: no Path B _wait_settled in wraps.py")
        lines.append(voltage)
        lines.append(current_null if _stable_eps_a_null(model) else current_tight)
    else:
        lines.append(voltage)
    return lines


def format_measure_lines(model: ProductModel, test_id: str) -> list[str]:
    tid = str(test_id or "").strip().lower()
    block = wire_map_for_test(model, tid)
    dmm = block.get("dmm")
    if isinstance(dmm, list):
        sense = ", ".join(str(x).strip().upper() for x in dmm if str(x).strip())
    elif dmm not in (None, ""):
        sense = str(dmm).strip().upper()
    else:
        scope = block.get("scope") if isinstance(block.get("scope"), dict) else {}
        sense = "MSO " + ", ".join(str(k) for k in scope) if scope else "see wire_map"
    mode = lookup_pass_mode(model, tid, tid) or (model.pass_mode or {}).get(tid)
    extra = []
    if tid in ("voh",):
        extra.append("voh=min_only")
    elif tid in ("vol",):
        extra.append("vol=max_only")
    if mode:
        extra.append(str(mode))
    elif model.pass_mode:
        extra.append(str(dict(model.pass_mode)))
    return [f"Measure + pass_mode: DMM/MSO -> {sense}; {'; '.join(extra) if extra else 'unspec'}"]


def format_save_lines(
    model: ProductModel, test_id: str, dut_index: Any = None
) -> list[str]:
    paths = resolve_data_paths(model, test_id, dut_index)
    return [
        "Save path after run (folders only; do not invent Excel cells)",
        f"Excel golden_auto/auto (pretty never auto): {paths.get('excel')}",
        f"report: {paths.get('report')}",
        f"STS datalog: {paths.get('datalog')}",
        f"CSV auto overwrite (pretty never auto): {paths.get('csv')}",
        f"STS latest PDF: {paths.get('report_pdf') or 'report.pdf'}",
        f"records: {paths.get('records')}",
    ]


def format_fail_lines(
    model: ProductModel,
    test_id: str,
    err: str,
    dut_index: Any = None,
) -> list[str]:
    attach = attach_path_line(model, test_id, dut_index)
    return [
        f"FAIL: {str(err or '')[:160]}",
        "Capture scope PNG or phone photo of the FAIL",
        f"Attach path: {attach}",
        "Then Continue (next DUT) or Abort",
    ]


def format_handoff_begin(model: ProductModel, test_id: str) -> list[str]:
    lines: list[str] = []
    lines.extend(format_wire_lines(model, test_id))
    lines.extend(format_stimulus_lines(model, test_id))
    lines.extend(format_settle_lines(model, test_id))
    lines.extend(format_measure_lines(model, test_id))
    wp = model.workbook_policy if isinstance(model.workbook_policy, dict) else {}
    if wp or model.excel_plots:
        lines.append(
            "Excel fill/plot: golden_auto/auto Version workbook/ only "
            "(pretty/ultimate_manual never_auto_write)"
        )
    return lines


def pins_named_in_wire_map(model: ProductModel) -> set[str]:
    """Pin names referenced by wire_map. Must be a subset of CONFIRMED pins."""
    wm = model.wire_map if isinstance(model.wire_map, dict) else {}
    names: set[str] = set()

    def _add(spec: Any) -> None:
        if isinstance(spec, dict):
            pin = str(spec.get("pin") or "").strip().upper()
            if pin:
                names.add(pin)
        elif isinstance(spec, str) and spec.strip():
            names.add(spec.strip().upper())
        elif isinstance(spec, list):
            for item in spec:
                _add(item)

    for block_key in ("psu", "awg"):
        block = wm.get(block_key)
        if isinstance(block, dict):
            for spec in block.values():
                _add(spec)
    _add(wm.get("gnd"))
    for block in _wire_tests(model).values():
        if not isinstance(block, dict):
            continue
        _add(block.get("dmm"))
        scope = block.get("scope")
        if isinstance(scope, dict):
            for spec in scope.values():
                _add(spec)
    return names


def operator_pause(params: Any, title: str, checklist: Optional[list[str]] = None) -> bool:
    hook = getattr(params, "pause_hook", None) if params is not None else None
    if hook is None:
        return True
    items = list(checklist or [])
    try:
        return bool(hook(title, checklist=items))
    except TypeError:
        return bool(hook(title))


@contextmanager
def path_b_handoff(params: Any, model: ProductModel, test_id: str):
    """Continue prompts: wire, stimulus, settle, measure; FAIL attach; save path."""
    tid = str(test_id or "").strip().lower()
    if not wire_map_has_test(model, tid):
        yield
        return
    begin = format_handoff_begin(model, tid)
    if not operator_pause(params, f"Path B {tid}: verify wire map then Continue", begin):
        raise RuntimeError(f"{tid}: operator aborted wire-map verify")
    try:
        yield
    except Exception as exc:
        dut = getattr(params, "unit_index", None) if params is not None else None
        operator_pause(
            params,
            f"Path B {tid} FAIL: capture scope/photo",
            format_fail_lines(model, tid, str(exc), dut),
        )
        raise
    else:
        dut = getattr(params, "unit_index", None) if params is not None else None
        operator_pause(
            params,
            f"Path B {tid}: save paths",
            format_save_lines(model, tid, dut),
        )

