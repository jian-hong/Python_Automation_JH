"""Operator confirm gate — blocks worker until GUI Continue/Abort."""
from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Optional

from ate.core.events import OperatorPrompt, OperatorResponse
from ate.fixture.modes import mode_checklist


class OperatorGate:
    """Thread-safe wait for operator confirmation (future: STM auto-ack)."""

    def __init__(self, emit: Optional[Callable[[dict], None]] = None) -> None:
        self._emit = emit
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}
        self._responses: dict[str, OperatorResponse] = {}
        self._pending: Optional[OperatorPrompt] = None

    def pending(self) -> Optional[dict[str, Any]]:
        """Current prompt waiting for Continue (survives get_events drain / refresh)."""
        with self._lock:
            return self._pending.to_dict() if self._pending else None

    def request(
        self,
        title: str,
        fixture_mode: str = "",
        checklist: Optional[list[str]] = None,
        timeout_s: Optional[float] = None,
        *,
        kind: str = "config_change",
        dut_index: Optional[int] = None,
        next_hint: str = "",
        timeline_id: str = "",
        test_tag: str = "",
    ) -> bool:
        """Emit prompt and block. Returns True if Continue, False if Abort/timeout."""
        prompt_id = str(uuid.uuid4())
        if checklist is not None:
            items = list(checklist)
        elif kind == "dut_change":
            items = [
                f"Remove previous unit (if any)",
                f"Install DUT / Unit #{dut_index} in the socket",
                "Confirm orientation / pin-1",
                "Close lid / clamp if used",
            ]
        elif kind == "channel_change":
            items = [
                "Confirm BUFFER / voltage-follower board is ready",
                "Move scope probes to Channel B (second half of DUT)",
                "Verify CH1 = IN+, CH2 = VOUT for Channel B",
                "Check RL / CL if required for this test",
            ]
        elif fixture_mode:
            items = mode_checklist(fixture_mode)
        else:
            items = ["Confirm setup, then Continue"]
        if next_hint:
            items = list(items) + [f"Next: {next_hint}"]

        prompt = OperatorPrompt(
            id=prompt_id,
            title=title,
            checklist=items,
            fixture_mode=fixture_mode,
            kind=kind,
            dut_index=dut_index,
            next_hint=next_hint,
            timeline_id=timeline_id,
            test_tag=test_tag,
        )
        ev = threading.Event()
        with self._lock:
            self._events[prompt_id] = ev
            self._pending = prompt

        if self._emit:
            self._emit({"type": "operator_prompt", "payload": prompt.to_dict()})

        ok = ev.wait(timeout=timeout_s)
        with self._lock:
            self._events.pop(prompt_id, None)
            if self._pending and self._pending.id == prompt_id:
                self._pending = None
            resp = self._responses.pop(prompt_id, None)

        if not ok or resp is None:
            return False
        return bool(resp.continue_)

    def respond(self, data: dict) -> None:
        resp = OperatorResponse.from_dict(data)
        with self._lock:
            self._responses[resp.prompt_id] = resp
            ev = self._events.get(resp.prompt_id)
            # Also accept respond without exact id if only one pending (UI recovery)
            if ev is None and self._pending is not None and len(self._events) == 1:
                only_id = next(iter(self._events))
                self._responses[only_id] = OperatorResponse(
                    prompt_id=only_id,
                    continue_=resp.continue_,
                    note=resp.note,
                )
                ev = self._events.get(only_id)
        if ev:
            ev.set()

    def abort_all(self) -> None:
        """Unblock any waiting request (STOP / emergency)."""
        with self._lock:
            pending_ids = list(self._events.keys())
            for pid in pending_ids:
                self._responses[pid] = OperatorResponse(prompt_id=pid, continue_=False)
                self._events[pid].set()
            self._pending = None
