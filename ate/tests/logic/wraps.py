"""Thin TestSpec wraps for repo-root logic_tests.py (A02-T01).

Do not import logic_tests at family load -- that module pulls scope_setup -> pyvisa.
Look up the golden body only when START actually runs the wrap.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from ate.core.registry import TestSpec, register
from ate.core.run_params import RunParams

_LOGIC_FIXTURE = "LOGIC"
_LEGACY: dict[str, Callable[..., dict[str, Any]]] | None = None


def _invoke_legacy(fn: Callable[..., dict[str, Any]], instr, params: RunParams):
    """Downloads/logic_tests.py IDD takes (vcca, vccb); repo-root takes (vcc)."""
    names = [
        p.name
        for p in inspect.signature(fn).parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and p.name != "instr"
        and p.default is inspect.Parameter.empty
    ]
    if "vccb" in names:
        vccb = params.vcc
        try:
            from ate.core.paths import PARTS_DIR
            import yaml

            raw = yaml.safe_load((PARTS_DIR / f"{params.part}.yaml").read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict) and raw.get("vccb") is not None:
                vccb = float(raw["vccb"])
        except Exception:
            pass
        return fn(instr, params.vcc, vccb)
    return fn(instr, params.vcc)


def _load_legacy() -> dict[str, Callable[..., dict[str, Any]]]:
    from logic_tests import (
        test_output_voltage,
        test_supply_current,
        test_tdis,
        test_ten,
        test_tidle,
        test_tp,
    )

    return {
        "tp": test_tp,
        "tidle": test_tidle,
        "tdis": test_tdis,
        "ten": test_ten,
        "supply_current": test_supply_current,
        "output_voltage": test_output_voltage,
    }


def _legacy_fn(key: str) -> Callable[..., dict[str, Any]]:
    global _LEGACY
    if _LEGACY is None:
        _LEGACY = _load_legacy()
    return _LEGACY[key]


def _register_vcc_test(
    *,
    test_id: str,
    label: str,
    lab_sheet: str,
    required: frozenset[str],
    legacy_key: str,
) -> None:
    def _run(instr, params: RunParams):
        data = _invoke_legacy(_legacy_fn(legacy_key), instr, params)
        keys = [k for k in data if k not in ("VCC", "VCCA", "VCCB")]
        summary = " ".join(f"{k}={data[k]}" for k in keys) if keys else f"VCC={data.get('VCC', params.vcc)}"
        return {"summary": summary, "data": data}

    register(
        TestSpec(
            id=test_id,
            label=label,
            required_instruments=required,
            fixture_mode=_LOGIC_FIXTURE,
            lab_sheet=lab_sheet,
            run=_run,
            dual_channel=False,
        )
    )


def _register_cap_load() -> None:
    def _run(instr, _params: RunParams):
        from logic_tests import test_cap_load

        data = test_cap_load(instr)
        return {
            "summary": f"CAP_pF={data.get('CAP_pF', float('nan'))}",
            "data": data,
        }

    register(
        TestSpec(
            id="cap_load",
            label="Capacitive Load",
            required_instruments=frozenset({"DMM"}),
            fixture_mode=_LOGIC_FIXTURE,
            lab_sheet="CapLoad",
            run=_run,
            dual_channel=False,
        )
    )


_register_vcc_test(
    test_id="tp",
    label="Propagation Delay (TP)",
    lab_sheet="TP",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_key="tp",
)
_register_vcc_test(
    test_id="tidle",
    label="Idle Propagation Delay (TIDLE)",
    lab_sheet="TIDLE",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_key="tidle",
)
_register_vcc_test(
    test_id="tdis",
    label="Output Disable Time (TDIS)",
    lab_sheet="TDIS",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_key="tdis",
)
_register_vcc_test(
    test_id="ten",
    label="Output Enable Time (TEN)",
    lab_sheet="TEN",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_key="ten",
)
_register_vcc_test(
    test_id="supply_current",
    label="Supply Current (IDD)",
    lab_sheet="IDD",
    required=frozenset({"PSU", "DMM"}),
    legacy_key="supply_current",
)
_register_vcc_test(
    test_id="output_voltage",
    label="Output Voltage",
    lab_sheet="VOUT",
    required=frozenset({"PSU", "DMM"}),
    legacy_key="output_voltage",
)
_register_cap_load()
