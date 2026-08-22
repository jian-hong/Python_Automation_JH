"""Event types for GUI <-> worker (operator prompts, progress, timeline, log)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class OperatorPrompt:
    """TestStand-style modal: worker blocks until Continue/Abort."""

    id: str
    title: str
    checklist: list[str] = field(default_factory=list)
    fixture_mode: str = ""
    require_confirm: bool = True
    kind: str = "config_change"  # dut_change | config_change | measure
    dut_index: int | None = None
    next_hint: str = ""
    timeline_id: str = ""
    test_tag: str = ""  # short names for gate dock, e.g. ORT or Settling+GBW

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OperatorResponse:
    prompt_id: str
    continue_: bool  # True = Continue, False = Abort
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperatorResponse":
        return cls(
            prompt_id=str(data.get("prompt_id", "")),
            continue_=bool(data.get("continue", data.get("continue_", False))),
            note=str(data.get("note", "")),
        )


@dataclass
class ProgressEvent:
    test_id: str
    status: str  # pending | running | pass | fail | skipped | waiting_operator
    message: str = ""
    data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LogEvent:
    text: str
    level: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
