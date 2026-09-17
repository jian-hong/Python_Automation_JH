"""Path B VIH/VIL search from recipe.search. Shared runner; no per-SKU fork.

limit-scaled first step: largest ladder step <= card |limit|.
on-hit: skip rest of this walk, rearm, next smaller step.
no reverse in a stage (VIH only up, VIL only down).

Do not invent a reverse sweep. Schmitt VT+/VT- use the same helper when
recipe.search is present. Missing search -> caller keeps threshold_step_v walk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class SearchError(RuntimeError):
    """Search cannot run (missing ladder / no step fits |limit|)."""


class SearchReverseError(SearchError):
    """A stage would reverse VIN. Verify FAIL bar."""


DEFAULT_LADDER = (0.5, 0.2, 0.1, 0.05, 0.01)


@dataclass
class SearchResult:
    vin: Optional[float]
    visited: list[float] = field(default_factory=list)
    first_step: Optional[float] = None
    samples: list[tuple[float, float]] = field(default_factory=list)


def search_blob(recipe: Any) -> dict[str, Any]:
    if isinstance(recipe, dict):
        raw = recipe.get("search")
        return dict(raw) if isinstance(raw, dict) else {}
    return {}


def step_ladder(search: dict[str, Any] | None) -> list[float]:
    raw = (search or {}).get("step_ladder_V") or DEFAULT_LADDER
    out: list[float] = []
    for item in raw:
        try:
            v = float(item)
        except (TypeError, ValueError):
            continue
        if v > 0:
            out.append(v)
    if not out:
        raise SearchError("recipe.search.step_ladder_V missing (do not invent steps)")
    return out


def first_step(ladder: list[float], limit: float | None) -> float:
    """Largest ladder step compatible with card |limit|.

    No |limit| -> finest ladder step (do not invent a coarse jump).
    No step <= |limit| -> FAIL (do not invent a step smaller than the ladder).
    """
    if not ladder:
        raise SearchError("empty step ladder")
    ordered = sorted({float(x) for x in ladder if float(x) > 0}, reverse=True)
    if not ordered:
        raise SearchError("empty step ladder")
    if limit is None:
        return ordered[-1]
    lim = abs(float(limit))
    ok = [s for s in ordered if s <= lim + 1e-12]
    if not ok:
        raise SearchError(f"no ladder step compatible with |limit|={lim}")
    return ok[0]


def finer_steps(ladder: list[float], current: float) -> list[float]:
    return [s for s in sorted(set(ladder), reverse=True) if s < float(current) - 1e-15]


def stage_points(arm: float, end: float, step: float, rising: bool) -> list[float]:
    """Monotonic VIN list. Never reverses."""
    step = float(step)
    if step <= 0:
        raise SearchError("step must be > 0")
    arm = float(arm)
    end = float(end)
    pts: list[float] = []
    if rising:
        if end + 1e-12 < arm:
            raise SearchReverseError("VIH stage end < arm (reverse)")
        v = arm
        while v <= end + 1e-12:
            pts.append(round(v, 9))
            nxt = v + step
            if nxt > end + 1e-12:
                if pts[-1] < end - 1e-12:
                    pts.append(round(end, 9))
                break
            if nxt <= v:
                raise SearchReverseError("VIH step did not advance")
            v = nxt
    else:
        if end - 1e-12 > arm:
            raise SearchReverseError("VIL stage end > arm (reverse)")
        v = arm
        while v + 1e-12 >= end:
            pts.append(round(v, 9))
            nxt = v - step
            if nxt < end - 1e-12:
                if pts[-1] > end + 1e-12:
                    pts.append(round(end, 9))
                break
            if nxt >= v:
                raise SearchReverseError("VIL step did not advance down")
            v = nxt
    assert_no_reverse(pts, rising)
    return pts


def assert_no_reverse(points: list[float], rising: bool) -> None:
    prev: float | None = None
    for v in points:
        if prev is None:
            prev = v
            continue
        if rising and v + 1e-12 < prev:
            raise SearchReverseError(f"VIH reverse {prev} -> {v}")
        if not rising and v - 1e-12 > prev:
            raise SearchReverseError(f"VIL reverse {prev} -> {v}")
        prev = v


def crossed(
    prev: Optional[float],
    vout: float,
    mid: float,
    y_expect: str,
    rising: bool,
) -> bool:
    if prev is None:
        return False
    track = str(y_expect or "track").lower() != "invert"
    went_high = prev < mid <= vout
    went_low = prev >= mid > vout
    if track:
        return went_high if rising else went_low
    return went_low if rising else went_high


def _arm_vin(spec: dict[str, Any], vcc: float, rising: bool) -> float:
    raw = spec.get("arm", 0.0 if rising else "VCC")
    if isinstance(raw, str) and raw.strip().upper() in ("VCC", "VDD", "RAIL"):
        return float(vcc)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0 if rising else float(vcc)


def _interpolate(
    samples: list[tuple[float, float]],
    *,
    mid: float,
    y_expect: str,
    rising: bool,
) -> Optional[float]:
    if len(samples) < 2:
        return samples[-1][0] if samples else None
    track = str(y_expect or "track").lower() != "invert"
    before_is_low = (track and rising) or ((not track) and (not rising))
    last_before: tuple[float, float] | None = None
    first_after: tuple[float, float] | None = None
    for vin, y in samples:
        is_high = y >= mid
        before = (not is_high) if before_is_low else is_high
        if before:
            last_before = (vin, y)
            first_after = None
        elif last_before is not None and first_after is None:
            first_after = (vin, y)
            break
    if last_before is None or first_after is None:
        return samples[-1][0]
    x0, y0 = last_before
    x1, y1 = first_after
    if abs(y1 - y0) < 1e-15:
        return x1
    return x0 + (mid - y0) * (x1 - x0) / (y1 - y0)


def run_search_stage(
    measure: Callable[[float], float],
    *,
    vcc: float,
    rising: bool,
    limit: float | None,
    search: dict[str, Any],
    y_expect: str = "track",
    mid: float | None = None,
) -> SearchResult:
    """Walk one edge (VIH up / VIL down). Returns interpolated VIN or last hit."""
    blob = search if isinstance(search, dict) else {}
    edge_key = "vih" if rising else "vil"
    spec = blob.get(edge_key) if isinstance(blob.get(edge_key), dict) else {}
    if spec.get("no_reverse_in_stage") is False:
        raise SearchReverseError("recipe.search forbids reverse; do not clear no_reverse_in_stage")
    direction = str(spec.get("direction") or ("up" if rising else "down")).strip().lower()
    if rising and direction in ("down", "falling", "reverse"):
        raise SearchReverseError("VIH direction must be up (no reverse)")
    if (not rising) and direction in ("up", "rising", "reverse"):
        raise SearchReverseError("VIL direction must be down (no reverse)")
    ladder = step_ladder(blob)
    first = first_step(ladder, limit)
    on_hit = blob.get("on_hit") if isinstance(blob.get("on_hit"), dict) else {}
    skip_rest = bool(on_hit.get("skip_rest_of_walk", True))
    rearm = bool(on_hit.get("rearm", True))
    next_smaller = bool(on_hit.get("next_smaller_step", True))
    try:
        frac = float(on_hit.get("restart_fraction_back") or 0.3)
    except (TypeError, ValueError):
        frac = 0.3
    after = blob.get("after_precision") if isinstance(blob.get("after_precision"), dict) else {}
    do_interp = bool(after.get("interpolate", True))
    mid_v = float(vcc) / 2.0 if mid is None else float(mid)
    arm = _arm_vin(spec, vcc, rising)
    end = float(vcc) if rising else 0.0
    visited: list[float] = []
    samples: list[tuple[float, float]] = []
    step = first
    prev: Optional[float] = None
    hit_vin: Optional[float] = None
    while step is not None:
        points = stage_points(arm, end, step, rising)
        hit_idx: Optional[int] = None
        for i, vin in enumerate(points):
            vout = float(measure(vin))
            visited.append(vin)
            samples.append((vin, vout))
            if crossed(prev, vout, mid_v, y_expect, rising):
                hit_vin = vin
                hit_idx = i
                if skip_rest:
                    break
            prev = vout
        if hit_idx is None or not next_smaller:
            break
        smaller = finer_steps(ladder, step)
        if not smaller:
            break
        if rearm:
            sign = 1.0 if rising else -1.0
            back = float(hit_vin) - sign * frac * float(step)
            has_pre = hit_idx is not None and hit_idx > 0
            pre = samples[hit_idx - 1][0] if has_pre else arm
            arm = min(pre, back) if rising else max(pre, back)
            arm = min(float(vcc), max(0.0, arm))
            prev = samples[hit_idx - 1][1] if has_pre else None
        step = smaller[0]
    vin_out = (
        _interpolate(samples, mid=mid_v, y_expect=y_expect, rising=rising)
        if do_interp
        else hit_vin
    )
    return SearchResult(vin=vin_out, visited=visited, first_step=first, samples=samples)
