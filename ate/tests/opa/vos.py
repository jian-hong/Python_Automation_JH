"""VOS DC sweep — wraps production opa_tests.test_vos_sweep."""
from __future__ import annotations

from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams


def _run(instr, params: RunParams):
    from ate_runner import timestamped_sheet_name
    from opa_tests import test_vos_sweep

    sheet = timestamped_sheet_name("vos sweep")
    fit = test_vos_sweep(
        instr,
        vcc=params.vcc,
        gain=params.gain,
        excel_path=params.research_excel,
        sheet_name=sheet,
    )
    return {
        "summary": f"VOS={fit.get('vos_mV', float('nan')):.4f} mV  R²={fit.get('r_squared', float('nan')):.6f}",
        "fit": fit,
        "lab_sheet": "VOS",
    }


register(
    TestSpec(
        id="vos_sweep",
        label="VOS DC Sweep",
        required_instruments=frozenset({"MSO", "PSU", "AWG"}),
        fixture_mode="G201",
        lab_sheet="VOS",
        run=_run,
        notes="RESEARCH board only (G201≈201) — not the general lab testboard",
    )
)
