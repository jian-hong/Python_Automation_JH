"""AC gain check — wraps opa_tests.test_ac_gain_check."""
from __future__ import annotations

from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams


def _run(instr, params: RunParams):
    from ate_runner import timestamped_sheet_name
    from opa_tests import test_ac_gain_check

    data = test_ac_gain_check(
        instr,
        vcc=params.vcc,
        freq_hz=params.freq_hz,
        amp_vpp=params.amp_vpp,
        gain_nominal=params.gain,
        excel_path=params.research_excel,
        sheet_name=timestamped_sheet_name("ac gain check"),
    )
    return {
        "summary": (
            f"gain={data.get('gain_vs_commanded', float('nan')):.4f} "
            f"loop={'OK' if data.get('loop_ok') else 'CHECK'}"
        ),
        "data": data,
    }


register(
    TestSpec(
        id="ac_gain_check",
        label="AC Gain Check",
        required_instruments=frozenset({"MSO", "PSU", "AWG"}),
        fixture_mode="G201",
        lab_sheet="VOS",
        run=_run,
    )
)
