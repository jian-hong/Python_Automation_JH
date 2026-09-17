"""Visa-free START parameters.

Family TestSpec modules import RunParams from here so load_family("logic")
does not pull ate.core.runner -> mso5072 -> scope_setup -> pyvisa.

ate.core.runner re-exports RunParams for the worker / START path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ate.core.database import get_context
from ate.core.paths import RESEARCH_EXCEL_PATH


@dataclass
class RunParams:
    vcc: float = 5.0
    gain: float = 1.0  # general board default (buffer); overwritten per fixture batch
    freq_hz: float = 500.0
    amp_vpp: float = 0.004
    n_repeats: int = 3
    lab_report: str = ""
    research_excel: str = str(RESEARCH_EXCEL_PATH)
    reset_before_run: bool = False
    unit_index: int = 1
    dut_indices: list[int] = field(default_factory=list)  # empty -> [unit_index]
    part: str = "rs622"
    channel: str = "CHA"
    channels: list[str] = field(default_factory=list)
    run_batch_id: str = ""  # shared across CHA/CHB for one DUT run -> one JSON
    run_label: str = ""  # operator name for this run (e.g. G11_1k_10k)
    gain_profile: str = "default"  # ate/config/parts gain_profiles key
    rf: str = ""  # RF network label (10k, 1k, ...)
    ri: str = ""  # RI network label
    current_limit_a: float = 0.10
    vccb: Optional[float] = None  # dual-rail Logic; None = part yaml
    progress_hook: Optional[Callable[..., None]] = field(default=None, repr=False)
    pause_hook: Optional[Callable[[str], bool]] = field(default=None, repr=False)

    def resolved_duts(self) -> list[int]:
        if self.dut_indices:
            return [int(d) for d in self.dut_indices]
        return [int(self.unit_index)]

    def resolved_channels(self) -> list[str]:
        order = ("CHA", "CHB")
        if self.channels:
            picked = {str(c).upper() for c in self.channels}
            return [c for c in order if c in picked] or ["CHA"]
        ch = (self.channel or "CHA").upper()
        return [ch if ch in order else "CHA"]

    def resolved_lab_report(self) -> str:
        if self.lab_report:
            return self.lab_report
        return str(get_context().lab_report_path())
