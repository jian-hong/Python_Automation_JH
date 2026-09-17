"""Datasheet min/typ/max for one part. Pass/fail lives here, not in each TestSpec.

Specs are ate/config/limits/<key>.yaml then part yaml `specs:`.
Never a RUN-IC catalog dump into #Test_Database.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from ate.core.paths import CONFIG_DIR, PARTS_DIR

LIMITS_DIR = CONFIG_DIR / "limits"


def _num(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def load_part_yaml(part_key: str = "") -> dict[str, Any]:
    pk = str(part_key or "").strip().lower()
    if not pk:
        return {}
    path = PARTS_DIR / f"{pk}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def normalize_pass_mode(raw: Any) -> str:
    """Canonical: range | min-only | max-only | empty."""
    s = str(raw or "").strip().lower().replace("_", "-")
    if s in ("min-only", "min"):
        return "min-only"
    if s in ("max-only", "max"):
        return "max-only"
    if s in ("range", "minmax", "min-max"):
        return "range"
    return ""


def infer_pass_mode(spec: dict[str, Any]) -> str:
    """DC Spec defaults when yaml omits pass_mode. Empty if still unknown."""
    existing = normalize_pass_mode(spec.get("pass_mode"))
    if existing:
        return existing
    sid = str(spec.get("id") or "").strip().upper()
    test = str(spec.get("test") or "").strip().lower()
    if any(tok in sid for tok in ("VTPLUS", "VTMINUS", "HYST", "VCC_")):
        return "range"
    if sid.startswith("VIH") or sid.startswith("VOH") or test in ("vih", "voh", "voh_load"):
        return "min-only"
    if sid.startswith("VIL") or sid.startswith("VOL") or test in ("vil", "vol", "vol_load"):
        return "max-only"
    if any(tok in sid for tok in ("ICC", "DELTA_ICC", "IOZ", "IOFF", "IIN")) or sid.startswith("II_"):
        return "max-only"
    if test in ("icc", "delta_icc", "ii", "ioz", "ioff", "ioff_leakage", "input_leakage_sweep"):
        return "max-only"
    if spec.get("min") is not None and spec.get("max") is not None:
        return "range"
    if spec.get("max") is not None and spec.get("min") is None:
        return "max-only"
    if spec.get("min") is not None and spec.get("max") is None:
        return "min-only"
    return ""


def load_part_specs(
    part_key: str = "",
    overlay: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    pk = str(part_key or "").strip().lower()
    rows: list[Any] = []
    lim = LIMITS_DIR / f"{pk}.yaml"
    if lim.is_file():
        blob = yaml.safe_load(lim.read_text(encoding="utf-8")) or {}
        if isinstance(blob, dict) and isinstance(blob.get("specs"), list):
            rows.extend(blob["specs"])
    data = load_part_yaml(pk)
    if isinstance(data.get("specs"), list):
        rows.extend(data["specs"])
    stacked: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        item = dict(row)
        item["id"] = str(item["id"]).strip()
        item["min"] = _num(item.get("min"))
        item["max"] = _num(item.get("max"))
        item["typ"] = _num(item.get("typ"))
        stacked[item["id"]] = item
    mode_overlay: dict[str, Any] = {}
    if isinstance(overlay, dict):
        inner = overlay.get("pass_mode") if isinstance(overlay.get("pass_mode"), dict) else overlay
        if isinstance(inner, dict):
            mode_overlay = {str(k): v for k, v in inner.items()}
    out: list[dict[str, Any]] = []
    for item in stacked.values():
        sid = item["id"]
        test = str(item.get("test") or "")
        if sid in mode_overlay:
            item["pass_mode"] = normalize_pass_mode(mode_overlay[sid])
        elif test in mode_overlay:
            item["pass_mode"] = normalize_pass_mode(mode_overlay[test])
        else:
            item["pass_mode"] = infer_pass_mode(item)
        out.append(item)
    return out


def test_info_map(part_key: str = "") -> dict[str, dict[str, Any]]:
    pk = str(part_key or "").strip().lower()
    out: dict[str, dict[str, Any]] = {}

    def _eat(block: Any) -> None:
        if not isinstance(block, dict):
            return
        for key, meta in block.items():
            if isinstance(meta, dict):
                out[str(key)] = dict(meta)
            elif isinstance(meta, str) and meta.strip():
                out[str(key)] = {"description": meta.strip()}

    lim = LIMITS_DIR / f"{pk}.yaml"
    if lim.is_file():
        blob = yaml.safe_load(lim.read_text(encoding="utf-8")) or {}
        if isinstance(blob, dict):
            _eat(blob.get("test_info"))
    _eat(load_part_yaml(pk).get("test_info"))
    return out


def load_part_datasheet(part_key: str = "") -> dict[str, Any]:
    pk = str(part_key or "").strip().lower()
    ds: dict[str, Any] = {}
    yml = load_part_yaml(pk).get("datasheet")
    if isinstance(yml, dict):
        ds.update(yml)
    lim = LIMITS_DIR / f"{pk}.yaml"
    if lim.is_file():
        blob = yaml.safe_load(lim.read_text(encoding="utf-8")) or {}
        if isinstance(blob, dict) and isinstance(blob.get("datasheet"), dict):
            ds.update(blob["datasheet"])
    return ds


def judge_value(value: Any, mn: Any, mx: Any, pass_mode: Any = None) -> str:
    """pass / fail / unspec. typ is display-only.

    pass_mode: range (both), min_only / min-only, max_only / max-only.
    Empty infers from whichever of min/max is present.
    """
    mode = normalize_pass_mode(pass_mode)
    if mode == "min-only":
        mx = None
    elif mode == "max-only":
        mn = None
    v = _num(value)
    lo = _num(mn)
    hi = _num(mx)
    if v is None or (lo is None and hi is None):
        return "unspec"
    if lo is not None and v < lo:
        return "fail"
    if hi is not None and v > hi:
        return "fail"
    return "pass"


def _test_aliases(tid: str) -> set[str]:
    t = str(tid or "").strip().lower()
    if not t:
        return set()
    groups = (
        {"supply_current", "supply_current_sweep", "icc"},
        {"delta_supply_current", "delta_icc"},
        {"input_thresholds", "input_threshold", "vth"},
        {"voh", "voh_load"},
        {"vol", "vol_load"},
        {"input_leakage_sweep", "ii"},
        {"ioz", "ioff", "ioff_leakage"},
    )
    for g in groups:
        if t in g:
            return set(g)
    return {t}


def specs_for_test(specs: list[dict[str, Any]], test_id: str) -> list[dict[str, Any]]:
    aliases = _test_aliases(test_id)
    tid = str(test_id or "").strip().lower()
    out: list[dict[str, Any]] = []
    for row in specs:
        test = str(row.get("test") or "").strip().lower()
        rid = str(row.get("id") or "").strip().lower()
        if test in aliases or rid == tid or rid in aliases:
            out.append(row)
    return out


def _spec_for(specs: list[dict[str, Any]], meas_id: str, test_id: str = "") -> dict[str, Any] | None:
    want = str(meas_id or "").strip().lower()
    aliases = _test_aliases(test_id)
    for row in specs:
        rid = str(row.get("id") or "").strip().lower()
        if rid == want:
            return row
    if aliases:
        for row in specs:
            if str(row.get("test") or "").strip().lower() in aliases:
                return row
    return None


def enrich_measurement(
    raw: dict[str, Any],
    *,
    specs: list[dict[str, Any]] | None = None,
    test_id: str = "",
    part_key: str = "",
) -> dict[str, Any]:
    row = dict(raw)
    sid = str(row.get("id") or row.get("name") or test_id or "").strip()
    if sid:
        row["id"] = sid
    spec = _spec_for(specs or [], sid, test_id)
    if spec:
        if row.get("min") is None and spec.get("min") is not None:
            row["min"] = spec["min"]
        if row.get("max") is None and spec.get("max") is not None:
            row["max"] = spec["max"]
        if row.get("typ") is None and spec.get("typ") is not None:
            row["typ"] = spec["typ"]
        if not row.get("unit") and spec.get("unit"):
            row["unit"] = spec["unit"]
        if not row.get("source") and spec.get("source"):
            row["source"] = spec["source"]
        if not normalize_pass_mode(row.get("pass_mode")) and spec.get("pass_mode"):
            row["pass_mode"] = spec["pass_mode"]
    if not normalize_pass_mode(row.get("pass_mode")) and part_key:
        try:
            from ate.tests.logic.product_model import has_product_model, load_product_model, lookup_pass_mode

            if has_product_model(part_key):
                model = load_product_model(part_key)
                if model is not None:
                    mode = lookup_pass_mode(model, sid, test_id)
                    if mode:
                        row["pass_mode"] = mode
        except Exception:
            pass
    if not normalize_pass_mode(row.get("pass_mode")):
        row["pass_mode"] = infer_pass_mode(row)
    row["result"] = judge_value(
        row.get("value"), row.get("min"), row.get("max"), pass_mode=row.get("pass_mode")
    )
    if row.get("greenable") is False and row.get("result") == "pass":
        row["result"] = "unspec"
        row.setdefault("note", "PROVISIONAL / UNCONFIRMED; not greenable")
    return row


def _flatten_numbers(blob: Any, prefix: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(blob, dict):
        if "value" in blob and (blob.get("id") or blob.get("name") or prefix):
            item = dict(blob)
            item.setdefault("id", blob.get("id") or blob.get("name") or prefix)
            out.append(item)
            return out
        for key, val in blob.items():
            if key in ("screenshot", "screenshots", "artifacts", "summary", "message"):
                continue
            kid = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out.append({"id": kid, "value": val})
            elif isinstance(val, (dict, list)):
                out.extend(_flatten_numbers(val, kid))
    elif isinstance(blob, list):
        for i, val in enumerate(blob):
            out.extend(_flatten_numbers(val, f"{prefix}[{i}]" if prefix else str(i)))
    return out


def measurements_from_result(
    data: Any,
    *,
    test_id: str = "",
    part_key: str = "",
) -> list[dict[str, Any]]:
    specs = load_part_specs(part_key)
    blob = data if isinstance(data, dict) else {}
    raw = blob.get("measurements")
    rows: list[dict[str, Any]]
    if isinstance(raw, list) and raw:
        rows = [x for x in raw if isinstance(x, dict)]
    else:
        inner = blob.get("data") if isinstance(blob.get("data"), dict) else blob
        rows = _flatten_numbers(inner)
        if not rows and specs:
            hit = _spec_for(specs, test_id, test_id)
            if hit:
                rows = [{"id": hit["id"]}]
    out = [
        enrich_measurement(r, specs=specs, test_id=test_id, part_key=part_key)
        for r in rows
    ]
    if part_key:
        try:
            from ate.tests.logic.product_model import (
                has_product_model,
                is_unconfirmed_status,
                load_product_model,
            )

            if has_product_model(part_key):
                model = load_product_model(part_key)
                tid = str(test_id or "").strip().lower()
                uses_tt = tid in {"input_threshold", "vth", "voh", "vol"}
                if model is not None and uses_tt and is_unconfirmed_status(model.truth_table_status):
                    for m in out:
                        if m.get("result") == "pass":
                            m["result"] = "unspec"
                            m["greenable"] = False
                            m.setdefault(
                                "note",
                                f"truth_table.status={model.truth_table_status} not Datasheet-signed; not greenable",
                            )
                if model is not None:
                    block = (model.dc_limits or {}).get(tid)
                    if isinstance(block, dict) and is_unconfirmed_status(block.get("status")):
                        for m in out:
                            if m.get("result") == "pass":
                                m["result"] = "unspec"
                                m["greenable"] = False
                                m.setdefault("note", "dc_limits PROVISIONAL; not greenable")
        except Exception:
            pass
    return [m for m in out if m.get("id")]


def mock_demo_measurements(test_id: str, *, part_key: str = "") -> list[dict[str, Any]]:
    specs = load_part_specs(part_key)
    tid = str(test_id or "").strip().lower()
    aliases = _test_aliases(tid)
    picked = [
        s
        for s in specs
        if str(s.get("test") or "").strip().lower() in aliases
        or str(s.get("id") or "").strip().lower() == tid
    ]
    if not picked:
        return []
    out: list[dict[str, Any]] = []
    for spec in picked:
        val = spec.get("typ")
        if val is None and spec.get("min") is not None and spec.get("max") is not None:
            val = (float(spec["min"]) + float(spec["max"])) / 2.0
        elif val is None and spec.get("max") is not None:
            val = float(spec["max"])
        elif val is None and spec.get("min") is not None:
            val = float(spec["min"])
        out.append(
            enrich_measurement(
                {"id": spec["id"], "value": val, "unit": spec.get("unit") or ""},
                specs=specs,
                test_id=test_id,
            )
        )
    return out


def any_fail(measurements: list[dict[str, Any]] | None) -> bool:
    return any(str(m.get("result") or "") == "fail" for m in (measurements or []) if isinstance(m, dict))
