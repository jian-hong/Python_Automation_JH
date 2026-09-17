"""Logic DC product model -- part YAML, not per-chip Python.

Fields the runner already understands, plus the Logic DC block:

  enabled_tests          already filters the Run page
  vcc_sweep_list         already feeds Setup VCC dropdown + DC sweeps
  logic_inputs           alias of logic_dc.inputs
  oe                     {pin, active: high|low} when the part has OE / 3-state
  logic_dc.truth_table   H/L/Z/X rows (datasheet function table)
  logic_dc.threshold_isolation
                         sweep one pin; hold the rest so Y tracks (or inverts)

Do not scrape colleague Downloads trees. Fill truth tables from the in-repo
datasheet extract (ate/config/datasheets/text/<key>.txt) or leave a GAP note.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import yaml

from ate.core.paths import PARTS_DIR

_H = frozenset({"H", "1", "HIGH", "VCC", "TRUE"})
_L = frozenset({"L", "0", "LOW", "GND", "FALSE"})
_Z = frozenset({"Z", "HZ", "HIZ", "HI-Z", "HI_Z"})
_X = frozenset({"X", "-", "DC", "DONTCARE", "DON'T CARE", "*"})


def bit(raw: Any) -> str:
    s = str(raw).strip().upper()
    if s in _H:
        return "H"
    if s in _L:
        return "L"
    if s in _Z:
        return "Z"
    if s in _X:
        return "X"
    raise ValueError(f"logic level not H/L/Z/X: {raw!r}")


def vcc_tag(vcc: float) -> str:
    """1.65 -> 1p65, 2.3 -> 2p3, 3.0 -> 3p0 (spec id suffix)."""
    v = float(vcc)
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v))}p0"
    one = round(v, 1)
    if abs(v - one) < 1e-9:
        t = f"{one:.1f}"
        return t.replace(".", "p")
    t = f"{v:.2f}".rstrip("0")
    return t.replace(".", "p")


@dataclass(frozen=True)
class PinStim:
    src: str  # awg | psu
    ch: int


@dataclass(frozen=True)
class Isolation:
    sweep: str
    hold: dict[str, str]
    y_tracks: str  # pin name or not_<pin>


@dataclass
class OeSpec:
    pin: str
    active: str  # high | low


@dataclass
class LogicModel:
    part_key: str
    inputs: tuple[str, ...]
    output: str
    oe: Optional[OeSpec]
    truth: tuple[dict[str, str], ...]
    isolation: tuple[Isolation, ...]
    schmitt: bool
    stimulus: dict[str, PinStim]
    icc_vi: float
    icc_include_oe: bool
    ioff_vcc_list: tuple[float, ...]
    ioz_vcc: Optional[float]
    ioz_vo_list: tuple[float, ...]
    delta_icc_offset_v: float
    delta_icc_vcc_min: float
    threshold_step_v: float
    psu_vmax: float
    gaps: tuple[str, ...] = field(default_factory=tuple)

    @property
    def drive_pins(self) -> tuple[str, ...]:
        pins = list(self.inputs)
        if self.oe is not None and self.oe.pin not in pins:
            pins.append(self.oe.pin)
        return tuple(pins)

    @property
    def icc_pins(self) -> tuple[str, ...]:
        pins = list(self.inputs)
        if self.oe is not None and self.icc_include_oe and self.oe.pin not in pins:
            pins.append(self.oe.pin)
        return tuple(pins)

    def oe_inactive_level(self) -> str:
        if self.oe is None:
            raise ValueError("no OE pin")
        return "L" if self.oe.active == "high" else "H"

    def oe_active_level(self) -> str:
        if self.oe is None:
            raise ValueError("no OE pin")
        return "H" if self.oe.active == "high" else "L"


def load_part_yaml(part_key: str) -> dict[str, Any]:
    key = str(part_key or "").strip().lower()
    if not key:
        return {}
    path = PARTS_DIR / f"{key}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def load_logic_model(part_key: str) -> Optional[LogicModel]:
    """None when the part has no logic_dc / logic_inputs block (Ariff 2-input fallback)."""
    raw = load_part_yaml(part_key)
    block = raw.get("logic_dc") if isinstance(raw.get("logic_dc"), dict) else {}
    inputs_raw = raw.get("logic_inputs") or block.get("inputs")
    truth_raw = raw.get("truth_table") or block.get("truth_table")
    if not inputs_raw and not truth_raw:
        return None
    inputs = tuple(str(x).strip() for x in (inputs_raw or []) if str(x).strip())
    if not inputs:
        raise ValueError(f"{part_key}: logic_inputs / logic_dc.inputs empty")
    output = str(block.get("output") or raw.get("logic_output") or "Y").strip() or "Y"
    oe = _parse_oe(raw.get("oe") if raw.get("oe") is not None else block.get("oe"))
    truth = _parse_truth(truth_raw or [], inputs, output, oe)
    isolation = _parse_isolation(
        block.get("threshold_isolation") or raw.get("threshold_isolation") or [],
        inputs,
        oe,
    )
    stim = _parse_stimulus(
        block.get("stimulus") or raw.get("stimulus") or {},
        inputs,
        oe,
    )
    gaps = block.get("gaps") or raw.get("logic_dc_gaps") or []
    ioz_vcc = block.get("ioz_vcc", raw.get("ioz_vcc"))
    return LogicModel(
        part_key=str(part_key or "").strip().lower(),
        inputs=inputs,
        output=output,
        oe=oe,
        truth=tuple(truth),
        isolation=tuple(isolation),
        schmitt=bool(block.get("schmitt", raw.get("schmitt", False))),
        stimulus=stim,
        icc_vi=float(block.get("icc_vi", raw.get("icc_vi", 5.5))),
        icc_include_oe=bool(block.get("icc_include_oe", True)),
        ioff_vcc_list=_floats(
            raw.get("ioff_vcc_list") or block.get("ioff_vcc_list") or [0.0]
        ),
        ioz_vcc=float(ioz_vcc) if ioz_vcc not in (None, "") else None,
        ioz_vo_list=_floats(block.get("ioz_vo_list") or [0.0, 5.5]),
        delta_icc_offset_v=float(block.get("delta_icc_offset_v", 0.6)),
        delta_icc_vcc_min=float(block.get("delta_icc_vcc_min", 3.0)),
        threshold_step_v=float(block.get("threshold_step_v", 0.05)),
        psu_vmax=float(block.get("psu_vmax", 5.0)),
        gaps=tuple(str(g) for g in gaps if str(g).strip()),
    )


def eval_y(model: LogicModel, levels: dict[str, str]) -> str:
    """Match the most specific truth-table row. X is don't-care."""
    best: Optional[str] = None
    best_score = -1
    pins = model.drive_pins
    got = {p: bit(levels[p]) if p in levels else "X" for p in pins}
    for row in model.truth:
        score = 0
        ok = True
        for p in pins:
            want = row.get(p, "X")
            have = got.get(p, "X")
            if want == "X":
                continue
            if have == "X":
                continue
            if want != have:
                ok = False
                break
            score += 1
        if ok and score > best_score:
            best = row[model.output]
            best_score = score
    if best is None:
        raise ValueError(f"{model.part_key}: no truth row for {got}")
    return best


def rail_combos(pins: Iterable[str]) -> list[dict[str, str]]:
    names = [str(p) for p in pins]
    n = len(names)
    if n == 0:
        return [{}]
    if n > 8:
        raise ValueError(f"refusing 2^{n} ICC combos")
    rows: list[dict[str, str]] = []
    for i in range(2 ** n):
        row = {names[b]: ("H" if (i >> b) & 1 else "L") for b in range(n)}
        rows.append(row)
    return rows


def isolation_errors(model: LogicModel) -> list[str]:
    """Hold vector must make Y change when the swept pin flips."""
    errors: list[str] = []
    if not model.isolation:
        errors.append(f"{model.part_key}: threshold_isolation empty")
        return errors
    for spec in model.isolation:
        if spec.sweep not in model.drive_pins:
            errors.append(f"{model.part_key}: isolation sweep {spec.sweep!r} not a drive pin")
            continue
        low = {**spec.hold, spec.sweep: "L"}
        high = {**spec.hold, spec.sweep: "H"}
        try:
            y_l = eval_y(model, low)
            y_h = eval_y(model, high)
        except Exception as exc:
            errors.append(f"{model.part_key}: isolation {spec.sweep}: {exc}")
            continue
        if y_l == "Z" or y_h == "Z":
            errors.append(
                f"{model.part_key}: isolation {spec.sweep} yields Y=Z "
                f"(hold OE active so Y tracks)"
            )
            continue
        if y_l == y_h:
            errors.append(
                f"{model.part_key}: isolation {spec.sweep} hold {spec.hold} "
                f"does not change Y (both {y_l})"
            )
            continue
        want = spec.y_tracks
        if want == spec.sweep and not (y_l == "L" and y_h == "H"):
            errors.append(
                f"{model.part_key}: {spec.sweep} should track (L->L, H->H), "
                f"got {y_l}/{y_h}"
            )
        if want in {f"not_{spec.sweep}", f"~{spec.sweep}"} and not (
            y_l == "H" and y_h == "L"
        ):
            errors.append(
                f"{model.part_key}: {spec.sweep} should invert, got {y_l}/{y_h}"
            )
    return errors


def _floats(raw: Any) -> tuple[float, ...]:
    if not isinstance(raw, list) or not raw:
        return tuple()
    return tuple(float(x) for x in raw)


def _parse_oe(raw: Any) -> Optional[OeSpec]:
    if not raw:
        return None
    if isinstance(raw, str):
        return OeSpec(pin=raw.strip(), active="high")
    if not isinstance(raw, dict):
        raise ValueError(f"oe must be dict or pin name, got {raw!r}")
    pin = str(raw.get("pin") or raw.get("name") or "OE").strip()
    act = str(raw.get("active") or raw.get("oe_active") or "high").strip().lower()
    if act in {"1", "h", "true"}:
        act = "high"
    if act in {"0", "l", "false"}:
        act = "low"
    if act not in {"high", "low"}:
        raise ValueError(f"oe.active must be high|low, got {act!r}")
    return OeSpec(pin=pin, active=act)


def _parse_truth(
    raw: Any,
    inputs: tuple[str, ...],
    output: str,
    oe: Optional[OeSpec],
) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("truth_table missing")
    pins = list(inputs)
    if oe is not None and oe.pin not in pins:
        pins.append(oe.pin)
    rows: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"truth row must be mapping, got {item!r}")
        row: dict[str, str] = {}
        for p in pins:
            if p not in item:
                row[p] = "X"
            else:
                row[p] = bit(item[p])
        if output not in item:
            raise ValueError(f"truth row missing {output}: {item}")
        row[output] = bit(item[output])
        rows.append(row)
    return rows


def _parse_isolation(
    raw: Any,
    inputs: tuple[str, ...],
    oe: Optional[OeSpec],
) -> list[Isolation]:
    if not isinstance(raw, list):
        return []
    known = set(inputs)
    if oe is not None:
        known.add(oe.pin)
    out: list[Isolation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sweep = str(item.get("sweep") or item.get("pin") or "").strip()
        if not sweep:
            continue
        hold_raw = item.get("hold") if isinstance(item.get("hold"), dict) else {}
        hold = {str(k): bit(v) for k, v in hold_raw.items()}
        tracks = str(item.get("y_tracks") or item.get("tracks") or sweep).strip()
        out.append(Isolation(sweep=sweep, hold=hold, y_tracks=tracks))
        extra = set(hold) - known
        if extra:
            raise ValueError(f"isolation hold pins not on device: {sorted(extra)}")
    return out


def _parse_stimulus(
    raw: Any,
    inputs: tuple[str, ...],
    oe: Optional[OeSpec],
) -> dict[str, PinStim]:
    """Default: AWG CH1/CH2 for first two drive pins, PSU CH3 for the rest, Y_force PSU CH2."""
    out: dict[str, PinStim] = {}
    if isinstance(raw, dict):
        for key, val in raw.items():
            if not isinstance(val, dict):
                continue
            src = str(val.get("src") or val.get("inst") or "").strip().lower()
            ch = int(val.get("ch") or val.get("channel") or 0)
            if src in {"awg", "gen"} and ch:
                out[str(key)] = PinStim("awg", ch)
            elif src in {"psu"} and ch:
                out[str(key)] = PinStim("psu", ch)
    drive = list(inputs)
    if oe is not None and oe.pin not in drive:
        drive.append(oe.pin)
    awg_ch = 1
    for pin in drive:
        if pin in out:
            continue
        if awg_ch <= 2:
            out[pin] = PinStim("awg", awg_ch)
            awg_ch += 1
        else:
            out[pin] = PinStim("psu", 3)
    out.setdefault("Y_force", PinStim("psu", 2))
    out.setdefault("VCC", PinStim("psu", 1))
    return out
