"""AC Vin sweep — wraps opa_tests.test_ac_vin_sweep (JPEG embeds)."""
from __future__ import annotations

from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams


def _run(instr, params: RunParams):
    from opa_tests import test_ac_vin_sweep

    data = test_ac_vin_sweep(
        instr,
        vcc=params.vcc,
        freq_hz=params.freq_hz,
        amp_vpp=params.amp_vpp,
        gain=params.gain,
        n_repeats=params.n_repeats,
        excel_path=params.research_excel,
    )
    n = len(data.get("repeats") or [])
    return {"summary": f"AC Vin {n} repeat(s) written", "data": data}


register(
    TestSpec(
        id="ac_vin_sweep",
        label="AC Vin Sweep (−5…+5 mV)",
        required_instruments=frozenset({"MSO", "PSU", "AWG"}),
        fixture_mode="G201",
        lab_sheet="VOS",
        run=_run,
    )
)
