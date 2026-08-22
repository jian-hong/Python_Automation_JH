"""STM / relay bridge stub — same OperatorGate events when hardware arrives."""
from __future__ import annotations

from typing import Any


class StmBridge:
    """Future: UART/USB to STM that switches PCB relays for FixtureMode.

    Today: dry-run only. When ready, ``apply_mode`` will drive relays and
    auto-ack the operator prompt so the UI modal can be skipped.
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.last_mode: str | None = None

    def apply_mode(self, mode: str) -> dict[str, Any]:
        self.last_mode = mode
        if not self.enabled:
            return {
                "ok": False,
                "mode": mode,
                "message": "STM bridge disabled — use operator checklist",
                "auto_ack": False,
            }
        # Placeholder for future serial protocol
        return {
            "ok": True,
            "mode": mode,
            "message": f"STM applied mode {mode}",
            "auto_ack": True,
        }
