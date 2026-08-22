"""Thin TestSpec wraps for repo-root logic_tests.py (A02-T01)."""
from __future__ import annotations

from typing import Any, Callable

from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams

_LOGIC_FIXTURE = "LOGIC"


def _register_vcc_test(
    *,
    test_id: str,
    label: str,
    lab_sheet: str,
    required: frozenset[str],
    legacy_fn: Callable[..., dict[str, Any]],
) -> None:
    def _run(instr, params: RunParams):
        data = legacy_fn(instr, params.vcc)
        keys = [k for k in data if k != "VCC"]
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


def _load_legacy():
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


_legacy = _load_legacy()

_register_vcc_test(
    test_id="tp",
    label="Propagation Delay (TP)",
    lab_sheet="TP",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_fn=_legacy["tp"],
)
_register_vcc_test(
    test_id="tidle",
    label="Idle Propagation Delay (TIDLE)",
    lab_sheet="TIDLE",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_fn=_legacy["tidle"],
)
_register_vcc_test(
    test_id="tdis",
    label="Output Disable Time (TDIS)",
    lab_sheet="TDIS",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_fn=_legacy["tdis"],
)
_register_vcc_test(
    test_id="ten",
    label="Output Enable Time (TEN)",
    lab_sheet="TEN",
    required=frozenset({"MSO", "PSU", "AWG"}),
    legacy_fn=_legacy["ten"],
)
_register_vcc_test(
    test_id="supply_current",
    label="Supply Current (IDD)",
    lab_sheet="IDD",
    required=frozenset({"PSU", "DMM"}),
    legacy_fn=_legacy["supply_current"],
)
_register_vcc_test(
    test_id="output_voltage",
    label="Output Voltage",
    lab_sheet="VOUT",
    required=frozenset({"PSU", "DMM"}),
    legacy_fn=_legacy["output_voltage"],
)
_register_cap_load()
