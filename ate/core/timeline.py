"""Run timeline — planned steps, progress, next action, history."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

MYT = timezone(timedelta(hours=8))

# Registry short tags — extend when adding new tests; unknown ids fall back to ID.upper()
_SHORT = {
    "settling": "Settling",
    "ort": "ORT",
    "gbw": "GBW",
    "slew": "Slew",
    "vos_sweep": "VOS",
    "ac_gain_check": "ACGain",
    "ac_vin_sweep": "ACVin",
}


def short_test_tag(spec_or_id: Any) -> str:
    tid = getattr(spec_or_id, "id", None) or str(spec_or_id)
    custom = getattr(spec_or_id, "short_tag", None)
    if custom:
        return str(custom)
    return _SHORT.get(str(tid), str(tid).replace("_", " ").title()[:14])


def short_batch_tag(specs: list[Any]) -> str:
    return "+".join(short_test_tag(s) for s in specs) if specs else ""


def _now() -> str:
    return datetime.now(MYT).isoformat(timespec="seconds")


@dataclass
class TimelineEntry:
    """One row on the operator timeline."""

    id: str
    kind: str  # dut_change | config_change | channel_change | test | session
    label: str
    status: str = "pending"  # pending | waiting | running | done | fail | skipped
    dut: int | None = None
    channel: str = ""
    fixture_mode: str = ""
    test_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    next_hint: str = ""
    test_tag: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Timeline:
    """Mutable plan shown live in the Run page."""

    entries: list[TimelineEntry] = field(default_factory=list)
    session_id: str = ""
    current_id: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        total = len(self.entries)
        done = sum(1 for e in self.entries if e.status in ("done", "fail", "skipped"))
        waiting = next((e for e in self.entries if e.status == "waiting"), None)
        running = next((e for e in self.entries if e.status == "running"), None)
        pending = [e for e in self.entries if e.status == "pending"]
        history = [e for e in self.entries if e.status in ("done", "fail", "skipped")]
        current = waiting or running
        nxt = pending[0] if pending else None
        pct = int(round(100.0 * done / total)) if total else 0
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress_pct": pct,
            "done_count": done,
            "total_count": total,
            "current": current.to_dict() if current else None,
            "next": nxt.to_dict() if nxt else None,
            "waiting": waiting.to_dict() if waiting else None,
            "history": [e.to_dict() for e in history],
            "upcoming": [e.to_dict() for e in pending[:8]],
            "entries": [e.to_dict() for e in self.entries],
        }

    def get(self, entry_id: str) -> Optional[TimelineEntry]:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def mark(
        self,
        entry_id: str,
        status: str,
        message: str = "",
        *,
        start: bool = False,
        finish: bool = False,
    ) -> TimelineEntry | None:
        e = self.get(entry_id)
        if e is None:
            return None
        e.status = status
        if message:
            e.message = message
        if start and not e.started_at:
            e.started_at = _now()
        if finish:
            e.finished_at = _now()
        self.current_id = entry_id
        return e


def build_plan(
    *,
    dut_indices: list[int],
    batches: list[tuple[str, list[Any]]],
    gains: dict[str, float],
    channels: list[str] | None = None,
) -> list[TimelineEntry]:
    """Expand: category (board) → channel → all DUTs → tests in that category.

    Keeps the same PCB/fixture for every DUT+channel before the next board change.
    If only Channel B is selected, the plan starts on CHB.
    """
    chans = [c.upper() for c in (channels or ["CHA"])]
    multi_dut = len(dut_indices) > 1
    dual_any = any(
        getattr(s, "dual_channel", True)
        for _, specs in batches
        for s in specs
    )
    entries: list[TimelineEntry] = []
    n = 0
    last_channel: str | None = None
    single_dut_installed = False

    for mode, specs in batches:
        tag = short_batch_tag(specs)
        gain = gains.get(mode)
        gain_txt = f" (gain={gain:g})" if gain is not None else ""
        dual_mode = any(getattr(s, "dual_channel", True) for s in specs)

        n += 1
        entries.append(
            TimelineEntry(
                id=f"cfg_{n}",
                kind="config_change",
                label=f"{tag or mode} · board {mode}{gain_txt}",
                fixture_mode=mode,
                test_tag=tag,
                next_hint=f"Set board to {mode} for {tag or 'tests'}, then Continue",
            )
        )

        mode_chans = chans if dual_mode else [chans[0]]
        for channel in mode_chans:
            if dual_any and last_channel is not None and channel != last_channel:
                n += 1
                ch_label = "Channel A" if channel == "CHA" else "Channel B"
                scope = "all DUTs" if multi_dut else "this DUT"
                entries.append(
                    TimelineEntry(
                        id=f"ch_{n}",
                        kind="channel_change",
                        label=f"{tag} · {ch_label}",
                        channel=channel,
                        fixture_mode=mode,
                        test_tag=tag,
                        next_hint=(
                            f"Move probes to {ch_label} for {tag} ({scope}), then Continue"
                        ),
                    )
                )
            last_channel = channel

            for dut in dut_indices:
                ask_dut = multi_dut or not single_dut_installed
                if ask_dut:
                    n += 1
                    entries.append(
                        TimelineEntry(
                            id=f"dut_{n}",
                            kind="dut_change",
                            label=f"{tag} · DUT_{dut} · {channel}",
                            dut=dut,
                            channel=channel,
                            fixture_mode=mode,
                            test_tag=tag,
                            next_hint=f"Place unit #{dut} for {tag} ({channel}), then Continue",
                        )
                    )
                    if not multi_dut:
                        single_dut_installed = True

                for spec in specs:
                    if not getattr(spec, "dual_channel", True) and channel != mode_chans[0]:
                        continue
                    use_ch = (
                        channel if getattr(spec, "dual_channel", True) else mode_chans[0]
                    )
                    tid = getattr(spec, "id", str(spec))
                    st = short_test_tag(spec)
                    n += 1
                    ch_tag = f" · {use_ch}" if dual_any and len(chans) > 1 else ""
                    entries.append(
                        TimelineEntry(
                            id=f"test_{n}",
                            kind="test",
                            label=f"{st} · DUT_{dut}{ch_tag}",
                            dut=dut,
                            channel=use_ch,
                            fixture_mode=mode,
                            test_id=tid,
                            test_tag=st,
                            next_hint=f"Automated: {st} {use_ch}",
                        )
                    )
    return entries
