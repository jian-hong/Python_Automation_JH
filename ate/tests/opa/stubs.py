"""Registered stubs for remaining lab-report sheets (yellow / not automated)."""
from __future__ import annotations

from ate.core.registry import TestSpec, register
from ate.core.runner import RunParams


def _stub(name: str, sheet: str, mode: str):
    def _run(_instr, _params: RunParams):
        raise RuntimeError(
            f"{name} not automated yet — mark yellow on Summary / run manually. "
            f"Sheet={sheet}. See LabAutomation_14.7 Eugene recipes."
        )

    register(
        TestSpec(
            id=name.lower().replace(" ", "_"),
            label=name,
            required_instruments=frozenset({"MSO", "PSU", "AWG"}),
            fixture_mode=mode,
            lab_sheet=sheet,
            run=_run,
            enabled=True,
            notes="Stub — LabAutomation reference / future STM",
        )
    )


# BUFFER-batch companions (recipes exist but still operator-heavy)
# Settling Time → ate/tests/opa/settling.py (automated)
_stub("Small Signal Step Response", "SSSR", "BUFFER")
_stub("Large Signal Step Response", "LSSR", "BUFFER")
_stub("Phase Reversal Protection", "NoPhaseReversal", "BUFFER")
_stub("Power On Time", "PowerOnTime", "BUFFER")

# ATE / unsure
_stub("EMIRR", "EMIRR", "ATE")
_stub("PSRR", "PSRR", "ATE")
_stub("CMRR", "CMRR", "ATE")
_stub("AOL", "AOL", "ATE")
_stub("VOHL", "VOL", "ATE")
