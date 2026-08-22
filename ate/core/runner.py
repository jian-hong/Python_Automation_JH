"""Headless modular runner — DUT + fixture gates + live timeline."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ate.core.database import (
    begin_session,
    current_session,
    end_session,
    get_context,
    record_step,
)
from ate.core.paths import RESEARCH_EXCEL_PATH
from ate.core.registry import TestSpec, group_by_fixture, load_family
from ate.core.timeline import Timeline, build_plan, short_batch_tag, short_test_tag
from ate.drivers.mso5072 import capture_jpeg, is_visa_poison
from ate.fixture.modes import mode_gain, mode_checklist
from ate.fixture.operator import OperatorGate
from ate.fixture.stm_bridge import StmBridge
from ate.instruments.discovery import find_instruments
from ate.instruments.session import Instruments

MYT = timezone(timedelta(hours=8))


def ensure_screenshot_dir(test_folder: str = "ORT", dut_index: int | None = None):
    from ate.reporting.lab_report import ensure_screenshot_dir as _ens

    return _ens(test_folder, dut_index)


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
    dut_indices: list[int] = field(default_factory=list)  # empty → [unit_index]
    part: str = "rs622"
    channel: str = "CHA"
    channels: list[str] = field(default_factory=list)
    run_batch_id: str = ""  # shared across CHA/CHB for one DUT run → one JSON
    run_label: str = ""  # operator name for this run (e.g. G11_1k_10k)
    gain_profile: str = "default"  # ate/config/parts gain_profiles key
    rf: str = ""  # RF network label (10k, 1k, …)
    ri: str = ""  # RI network label
    current_limit_a: float = 0.10
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


@dataclass
class StepResult:
    test_id: str
    success: bool
    summary: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    dut: int | None = None
    channel: str = ""
    fixture_mode: str = ""


class ATECore:
    """Thread-safe bench orchestrator for Tauri / CLI clients."""

    def __init__(
        self,
        emit: Optional[Callable[[dict], None]] = None,
        stm_enabled: bool = False,
    ) -> None:
        self._emit = emit or (lambda _e: None)
        self._lock = threading.Lock()
        self._busy = False
        self._cancel_requested = False
        self._instr: Optional[Instruments] = None
        self._mapping: dict[str, str] = {}
        self._timeline: Optional[Timeline] = None
        self._last_run_results: list[StepResult] = []
        self.gate = OperatorGate(emit=self._emit)
        self.stm = StmBridge(enabled=stm_enabled)
        self._family = load_family()
        try:
            get_context().ensure_tree()
        except Exception:
            pass

    def _log(self, text: str) -> None:
        print(text)
        self._emit({"type": "log", "payload": {"text": text + "\n", "level": "info"}})

    def _progress(self, test_id: str, status: str, message: str = "", **extra: Any) -> None:
        payload: dict[str, Any] = {
            "test_id": test_id,
            "status": status,
            "message": message,
        }
        payload.update(extra)
        self._emit({"type": "progress", "payload": payload})

    def _emit_timeline(self) -> None:
        if self._timeline is None:
            return
        self._emit({"type": "timeline", "payload": self._timeline.to_dict()})

    def timeline_snapshot(self) -> dict[str, Any]:
        if self._timeline is None:
            return {}
        return self._timeline.to_dict()

    def load_family(self, family: str | None = None) -> str:
        """Switch active test family (clears registry, reloads package)."""
        self._family = load_family(family)
        return self._family

    @property
    def family(self) -> str:
        return self._family

    @property
    def session_open(self) -> bool:
        return self._instr is not None

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def discover(self) -> dict[str, str]:
        self._mapping = find_instruments()
        self._log(f"Discovered: {self._mapping}")
        return dict(self._mapping)

    def open_session(self) -> dict[str, str]:
        if self._instr is not None:
            self.close_session()
        # Always re-scan — stale Discover can miss DP832 if USB was busy
        self._mapping = find_instruments()
        self._log("Opening instrument session…")
        self._instr = Instruments(self._mapping or None)
        self._mapping = dict(self._instr.inst_map)
        missing = [k for k in ("MSO", "PSU", "AWG") if k not in self._mapping]
        if missing:
            self._log(f"WARNING missing: {missing} — check USB / close Ultra Sigma")
        self._log(f"Session open: {list(self._mapping)}")
        return dict(self._mapping)

    def close_session(self) -> None:
        if self._instr is None:
            return
        try:
            self._instr.close_all()
        finally:
            self._instr = None
            self._log("Session closed.")

    def capture_screenshot(self, prefix: str = "manual", test_key: str = "ORT") -> str:
        if self._instr is None or self._instr.scope is None:
            raise RuntimeError("Open Session first — need live MSO5072.")
        ctx = get_context()
        out = ensure_screenshot_dir(test_key, None)
        ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
        path = out / f"{prefix}_{ts}.jpg"
        self._log(f"MSO5072 JPEG → {path}")
        self._log(f"DB context: {ctx.component}/{ctx.part}/{ctx.package}/{ctx.version}")
        return capture_jpeg(self._instr.scope, path)

    def operator_respond(self, data: dict) -> None:
        self.gate.respond(data)

    def pending_operator(self) -> dict | None:
        return self.gate.pending()

    def last_run_results(self) -> list[dict[str, Any]]:
        return [
            {
                "test_id": r.test_id,
                "success": r.success,
                "summary": r.summary,
                "error": r.error,
                "dut": r.dut,
                "channel": r.channel,
                "fixture_mode": r.fixture_mode,
            }
            for r in self._last_run_results
        ]

    def _abort_remaining(self, results: list[StepResult], reason: str) -> None:
        if self._timeline is None:
            return
        for e in self._timeline.entries:
            if e.status == "pending":
                e.status = "skipped"
                e.message = reason
                e.finished_at = datetime.now(MYT).isoformat(timespec="seconds")
                if e.kind == "test" and e.test_id:
                    results.append(
                        StepResult(
                            test_id=e.test_id,
                            success=False,
                            error=reason,
                            dut=e.dut,
                            fixture_mode=e.fixture_mode,
                        )
                    )
                    record_step(
                        e.test_id,
                        success=False,
                        error=reason,
                        fixture_mode=e.fixture_mode,
                    )
                    self._progress(e.test_id, "skipped", reason, dut=e.dut)
        self._emit_timeline()

    def run_sequence(self, test_ids: list[str], params: RunParams) -> list[StepResult]:
        if self._instr is None:
            raise RuntimeError("Open Session first.")
        with self._lock:
            if self._busy:
                raise RuntimeError("Runner busy.")
            self._busy = True
            self._cancel_requested = False
        results: list[StepResult] = []
        status = "completed"
        try:
            ctx = get_context()
            ctx.ensure_tree()
            if not params.lab_report:
                params = replace(params, lab_report=str(ctx.lab_report_path()))

            duts = params.resolved_duts()
            channels = params.resolved_channels()
            batches = group_by_fixture(test_ids)
            gains = {m: mode_gain(m, params.part) for m, _ in batches}
            plan = [
                {"mode": m, "tests": [s.id for s in specs], "gain": gains[m]}
                for m, specs in batches
            ]

            entries = build_plan(
                dut_indices=duts,
                batches=batches,
                gains=gains,
                channels=channels,
            )
            self._timeline = Timeline(
                entries=entries,
                started_at=datetime.now(MYT).isoformat(timespec="seconds"),
            )
            self._emit_timeline()

            self._log(
                f"DB: {ctx.component}/{ctx.part}/{ctx.package}/{ctx.version} "
                f"model={ctx.model} DUTs={duts}"
            )
            self._log(f"Lab report: {params.lab_report}")
            self._log(f"Channels: {channels}")
            self._log(
                f"Plan: category → channel → DUTs "
                f"({len(batches)} cat × {len(channels)} ch × {len(duts)} DUT) "
                f"= {len(entries)} timeline steps"
            )
            self._log(
                "Fixture batches: "
                + " → ".join(f"{m}×{len(s)}" for m, s in batches)
            )

            begin_session(
                {
                    **{k: getattr(params, k) for k in (
                        "vcc", "freq_hz", "amp_vpp", "n_repeats",
                        "unit_index", "part", "reset_before_run",
                        "run_label", "gain_profile", "rf", "ri", "gain",
                        "current_limit_a",
                    )},
                    "dut_indices": duts,
                    "channels": channels,
                    "lab_report": params.lab_report,
                    "test_ids": list(test_ids),
                },
                instrument_map=self._mapping,
                fixture_plan=plan,
            )
            rs = current_session() or {}
            if self._timeline and rs.get("session_id"):
                self._timeline.session_id = str(rs["session_id"])
                self._emit_timeline()

            dut_batch_ids: dict[int, str] = {}
            modes_configured: set[str] = set()
            multi_dut = len(duts) > 1
            single_dut_installed = False
            last_channel: str | None = None

            for mode, specs in batches:
                if self._abort_if_cancelled(results):
                    status = "aborted"
                    break

                tag = short_batch_tag(specs)
                stm = self.stm.apply_mode(mode)

                cfg_entry = next(
                    (
                        e
                        for e in self._timeline.entries
                        if e.kind == "config_change"
                        and e.fixture_mode == mode
                        and e.status == "pending"
                    ),
                    None,
                )
                if cfg_entry is not None and mode in modes_configured:
                    self._timeline.mark(
                        cfg_entry.id,
                        "skipped",
                        f"{mode} auto — same config",
                        finish=True,
                    )
                    self._emit_timeline()
                    self._log(f"Config {mode} already confirmed — auto-continue")
                elif cfg_entry is not None and not stm.get("auto_ack"):
                    self._timeline.mark(cfg_entry.id, "waiting", start=True)
                    self._emit_timeline()
                    self._progress(
                        "",
                        "waiting_operator",
                        f"Fixture {mode}",
                        kind="config_change",
                        fixture_mode=mode,
                        timeline_id=cfg_entry.id,
                    )
                    g11_profile = bool(params.rf and params.ri and mode == "G11")
                    cfg_title = f"{tag} · board {mode}"
                    if g11_profile and params.run_label:
                        cfg_title = f"{tag} · board {mode} — {params.run_label}"
                    cfg_extra = (
                        [
                            f"Run: {params.run_label}" if params.run_label else "GBW G11",
                            f"RF={params.rf}, RI={params.ri}, gain={params.gain:.4g}",
                            "Confirm soldered network matches profile before Continue",
                        ]
                        if g11_profile
                        else None
                    )
                    ok = self._ask_operator(
                        title=cfg_title,
                        kind="config_change",
                        fixture_mode=mode,
                        test_tag=tag,
                        next_hint=cfg_entry.next_hint,
                        timeline_id=cfg_entry.id,
                        checklist=(
                            cfg_extra + mode_checklist(mode, params.part)
                            if cfg_extra
                            else None
                        ),
                    )
                    if not ok:
                        status = "aborted"
                        self._timeline.mark(
                            cfg_entry.id, "skipped", "Aborted", finish=True
                        )
                        self._abort_remaining(results, "Aborted at config prompt")
                        break
                    self._timeline.mark(
                        cfg_entry.id, "done", f"{mode} ready", finish=True
                    )
                    self._emit_timeline()
                    self._log(f"Config {mode} confirmed")
                    modes_configured.add(mode)
                elif cfg_entry is not None and stm.get("auto_ack"):
                    self._timeline.mark(
                        cfg_entry.id, "done", f"{mode} auto", finish=True
                    )
                    self._emit_timeline()
                    modes_configured.add(mode)

                if status == "aborted":
                    break

                dual_mode = any(getattr(s, "dual_channel", True) for s in specs)
                mode_chans = channels if dual_mode else [channels[0]]

                for channel in mode_chans:
                    if self._abort_if_cancelled(results):
                        status = "aborted"
                        break

                    if last_channel is not None and channel != last_channel:
                        ch_entry = next(
                            (
                                e
                                for e in self._timeline.entries
                                if e.kind == "channel_change"
                                and e.channel == channel
                                and e.fixture_mode == mode
                                and e.status == "pending"
                            ),
                            None,
                        )
                        if ch_entry is None:
                            ch_entry = next(
                                (
                                    e
                                    for e in self._timeline.entries
                                    if e.kind == "channel_change"
                                    and e.channel == channel
                                    and e.status == "pending"
                                ),
                                None,
                            )
                        if ch_entry is not None:
                            ch_name = (
                                "Channel A" if channel == "CHA" else "Channel B"
                            )
                            scope = "all DUTs" if multi_dut else f"DUT #{duts[0]}"
                            self._timeline.mark(ch_entry.id, "waiting", start=True)
                            self._emit_timeline()
                            self._progress(
                                "",
                                "waiting_operator",
                                f"{ch_name} — {scope}",
                                kind="channel_change",
                                channel=channel,
                                timeline_id=ch_entry.id,
                            )
                            ok = self._ask_operator(
                                title=f"{tag} · {ch_name} ({scope})",
                                kind="channel_change",
                                test_tag=tag,
                                dut_index=duts[0] if not multi_dut else None,
                                next_hint=ch_entry.next_hint,
                                timeline_id=ch_entry.id,
                            )
                            if not ok:
                                status = "aborted"
                                self._timeline.mark(
                                    ch_entry.id, "skipped", "Aborted", finish=True
                                )
                                self._abort_remaining(
                                    results, "Aborted at channel prompt"
                                )
                                break
                            self._timeline.mark(
                                ch_entry.id, "done", f"{ch_name} ready", finish=True
                            )
                            self._emit_timeline()
                            self._log(
                                f"{ch_name} confirmed — starting {scope} pass"
                            )

                    if status == "aborted":
                        break

                    last_channel = channel
                    prev_dut: int | None = None

                    for dut in duts:
                        if self._abort_if_cancelled(results):
                            status = "aborted"
                            break
                        if dut not in dut_batch_ids:
                            dut_batch_ids[dut] = datetime.now(MYT).strftime(
                                "%Y-%m-%d_%H%M%S"
                            )
                        dut_run_id = dut_batch_ids[dut]

                        ask_dut = multi_dut or not single_dut_installed
                        dut_entry = next(
                            (
                                e
                                for e in self._timeline.entries
                                if e.kind == "dut_change"
                                and e.dut == dut
                                and e.channel == channel
                                and e.fixture_mode == mode
                                and e.status == "pending"
                            ),
                            None,
                        )
                        if (
                            ask_dut
                            and dut_entry is not None
                            and (prev_dut is None or dut != prev_dut)
                        ):
                            is_change = prev_dut is not None
                            self._timeline.mark(dut_entry.id, "waiting", start=True)
                            self._emit_timeline()
                            self._progress(
                                "",
                                "waiting_operator",
                                f"{'Change' if is_change else 'Install'} DUT_{dut}",
                                kind="dut_change",
                                dut=dut,
                                channel=channel,
                                timeline_id=dut_entry.id,
                            )
                            title = f"{tag} · DUT #{dut} · {channel}"
                            checklist = (
                                [
                                    "Bench SAFE: PSU OFF, AWG OFF @ 1 kHz, scope STOP",
                                    f"Remove DUT #{prev_dut}",
                                    f"Install DUT #{dut}",
                                    "Confirm pin-1 orientation",
                                    "Then Continue (power comes back for the test)",
                                ]
                                if is_change
                                else [
                                    "Bench SAFE: PSU OFF, AWG OFF @ 1 kHz, scope STOP",
                                    f"Install DUT #{dut} in the socket",
                                    "Confirm pin-1 orientation",
                                    "Then Continue (power comes back for the test)",
                                ]
                            )
                            ok = self._ask_operator(
                                title=title,
                                kind="dut_change",
                                dut_index=dut,
                                test_tag=tag,
                                next_hint=dut_entry.next_hint,
                                timeline_id=dut_entry.id,
                                checklist=checklist,
                            )
                            if not ok:
                                status = "aborted"
                                self._timeline.mark(
                                    dut_entry.id, "skipped", "Aborted", finish=True
                                )
                                self._abort_remaining(
                                    results, "Aborted at DUT prompt"
                                )
                                break
                            self._timeline.mark(
                                dut_entry.id, "done", "DUT ready", finish=True
                            )
                            self._emit_timeline()
                            self._log(f"DUT_{dut} confirmed ({channel})")
                            if not multi_dut:
                                single_dut_installed = True
                        prev_dut = dut

                        for spec in specs:
                            use_ch = (
                                channel
                                if getattr(spec, "dual_channel", True)
                                else channels[0]
                            )
                            if (
                                not getattr(spec, "dual_channel", True)
                                and channel != mode_chans[0]
                            ):
                                continue

                            batch_params = replace(
                                params,
                                gain=(
                                    float(params.gain)
                                    if (params.rf and params.ri and mode == "G11")
                                    else mode_gain(mode, params.part)
                                ),
                                run_label=params.run_label if mode == "G11" else "",
                                rf=params.rf if mode == "G11" else "",
                                ri=params.ri if mode == "G11" else "",
                                unit_index=dut,
                                channel=use_ch,
                                run_batch_id=dut_run_id,
                            )

                            def _hook(
                                substep: str,
                                st: str,
                                msg: str,
                                *,
                                _spec=spec,
                                _dut=dut,
                                _ch=use_ch,
                            ) -> None:
                                self._progress(
                                    _spec.id,
                                    st,
                                    msg,
                                    dut=_dut,
                                    channel=_ch,
                                    substep=substep,
                                    fixture_mode=_spec.fixture_mode,
                                )

                            def _pause(
                                title: str,
                                *,
                                _dut=dut,
                                _spec=spec,
                            ) -> bool:
                                if _spec.id == "gbw":
                                    self._log(
                                        f"GBW checkpoint (auto-continue): {title}"
                                    )
                                    return True
                                return self._ask_operator(
                                    title=title,
                                    kind="config_change",
                                    dut_index=_dut,
                                    test_tag=short_test_tag(_spec),
                                    checklist=[
                                        "Confirm AWG CH1 output is ON",
                                        "Scope CH1=IN+, CH2=VOUT",
                                        "Then Continue",
                                    ],
                                )

                            batch_params.progress_hook = _hook
                            batch_params.pause_hook = _pause

                            test_entry = next(
                                (
                                    e
                                    for e in self._timeline.entries
                                    if e.kind == "test"
                                    and e.dut == dut
                                    and e.test_id == spec.id
                                    and e.channel == use_ch
                                    and e.fixture_mode == mode
                                    and e.status == "pending"
                                ),
                                None,
                            )
                            if test_entry is not None:
                                self._timeline.mark(
                                    test_entry.id, "running", start=True
                                )
                                self._emit_timeline()

                            if self._instr.scope is not None:
                                try:
                                    from scope_setup import recover_scope_session

                                    recover_scope_session(self._instr.scope)
                                    time.sleep(0.5 if dut and dut > 1 else 0.2)
                                except Exception as exc:
                                    self._log(f"scope recover DUT_{dut}: {exc}")

                            if self._abort_if_cancelled(results):
                                status = "aborted"
                                break

                            step = self._run_one(spec, batch_params, dut=dut)
                            self._safe_idle_for_operator(
                                reason=f"post DUT_{dut} {use_ch} {spec.id}"
                            )
                            if self._instr.scope is not None:
                                try:
                                    from scope_setup import park_scope_idle

                                    park_scope_idle(self._instr.scope, clear=True)
                                    time.sleep(0.35)
                                except Exception as exc:
                                    self._log(f"scope park post-test: {exc}")
                            results.append(step)

                            arts = []
                            if isinstance(step.data, dict):
                                for key in ("screenshot", "screenshots", "artifacts"):
                                    val = step.data.get(key)
                                    if isinstance(val, str):
                                        arts.append({"path": val})
                                    elif isinstance(val, list):
                                        arts.extend(
                                            {"path": p} if isinstance(p, str) else p
                                            for p in val
                                        )
                            record_step(
                                step.test_id,
                                success=step.success,
                                summary=step.summary,
                                error=step.error,
                                fixture_mode=spec.fixture_mode,
                                artifacts=arts or None,
                            )
                            if test_entry is not None:
                                self._timeline.mark(
                                    test_entry.id,
                                    "done" if step.success else "fail",
                                    step.summary or step.error,
                                    finish=True,
                                )
                                self._emit_timeline()

                            if not step.success:
                                err = step.error or step.summary or "failed"
                                st = short_test_tag(spec)
                                self._log(
                                    f"FAIL DUT_{dut} {use_ch} {spec.id}: {err}"
                                )
                                if is_visa_poison(err):
                                    self._log(
                                        "VISA SYSTEM_ERROR after retry — "
                                        "auto-continue next unit (no Continue popup)"
                                    )
                                    continue
                                ok = self._ask_operator(
                                    title=f"{st} · DUT #{dut} {use_ch} FAILED",
                                    kind="dut_change",
                                    dut_index=dut,
                                    test_tag=st,
                                    checklist=[
                                        f"Error: {err[:180]}",
                                        "Bench is SAFE IDLE (PSU/AWG OFF)",
                                        "Continue -> next DUT, or Abort to stop",
                                    ],
                                    next_hint="Continue to next unit, or Abort",
                                )
                                if not ok:
                                    status = "aborted"
                                    self._abort_remaining(
                                        results, "Aborted after DUT fail"
                                    )
                                    break

                        if status == "aborted":
                            break

                    if status == "aborted":
                        break

                if status == "aborted":
                    break
            if self._timeline:
                self._timeline.finished_at = datetime.now(MYT).isoformat(timespec="seconds")
                self._emit_timeline()
            self._safe_idle_for_operator(reason="sequence done")
            self._last_run_results = list(results)
            return results
        except Exception:
            status = "failed"
            self._safe_idle_for_operator(reason="sequence failed")
            raise
        finally:
            try:
                path = end_session(status=status)
                if path:
                    self._log(f"Session manifest → {path}")
            except Exception as exc:
                self._log(f"Session manifest write failed: {exc}")
            with self._lock:
                self._busy = False

    def _reopen_mso_after_visa(self) -> None:
        """USB/VISA SYSTEM_ERROR is not cleared by *CLS — drop and reopen MSO."""
        instr = self._instr
        if instr is None or instr.scope is None:
            return
        try:
            instr.reopen_scope()
            from scope_setup import recover_scope_session

            recover_scope_session(instr.scope, run=True)
            self._log("MSO reopened after VISA SYSTEM_ERROR")
        except Exception as exc:
            self._log(f"MSO reopen failed: {exc}")

    def _run_one(
        self, spec: TestSpec, params: RunParams, *, dut: int | None = None
    ) -> StepResult:
        assert self._instr is not None
        self._progress(
            spec.id,
            "running",
            spec.label,
            dut=dut,
            fixture_mode=spec.fixture_mode,
        )
        self._log(
            f"=== RUN {spec.label} (mode={spec.fixture_mode}, "
            f"DUT_{dut or params.unit_index}, {params.channel}) ==="
        )
        available = self._instr.available_devices()
        missing = sorted(spec.required_instruments - available)
        if missing:
            err = f"Missing instruments: {missing}"
            self._log(f"FAIL {spec.id}: {err}")
            self._progress(
                spec.id,
                "fail",
                err,
                dut=dut,
                fixture_mode=spec.fixture_mode,
            )
            return StepResult(
                test_id=spec.id,
                success=False,
                error=err,
                dut=dut,
                channel=params.channel,
                fixture_mode=spec.fixture_mode,
            )

        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                if attempt == 0:
                    if params.reset_before_run:
                        self._instr.reset_all()
                    if self._instr.scope is not None:
                        try:
                            from scope_setup import recover_scope_session

                            recover_scope_session(self._instr.scope)
                        except Exception as exc:
                            self._log(f"scope recover pre-run: {exc}")
                else:
                    self._log(
                        f"VISA retry {spec.id} attempt {attempt + 1} "
                        "(MSO reopen; PSU/AWG stay ON)"
                    )
                    self._reopen_mso_after_visa()

                data = spec.run(self._instr, params)
                summary = ""
                if isinstance(data, dict):
                    summary = str(data.get("summary") or data.get("message") or "OK")
                else:
                    summary = "OK"
                self._progress(
                    spec.id,
                    "pass",
                    summary,
                    dut=dut,
                    fixture_mode=spec.fixture_mode,
                )
                return StepResult(
                    test_id=spec.id,
                    success=True,
                    summary=summary,
                    data=data or {},
                    dut=dut,
                    channel=params.channel,
                    fixture_mode=spec.fixture_mode,
                )
            except Exception as exc:
                last_exc = exc
                self._log(f"FAIL {spec.id}: {exc}")
                if not is_visa_poison(exc) or attempt == 1:
                    break
                self._log(
                    f"VISA poison on {spec.id} — recover MSO and retry once "
                    "(PSU/AWG stay ON; no operator wait)"
                )

        err = str(last_exc) if last_exc is not None else "failed"
        self._progress(
            spec.id,
            "fail",
            err,
            dut=dut,
            fixture_mode=spec.fixture_mode,
        )
        return StepResult(
            test_id=spec.id,
            success=False,
            error=err,
            dut=dut,
            channel=params.channel,
            fixture_mode=spec.fixture_mode,
        )

    def request_cancel(self) -> None:
        """Signal run_sequence to abort (used by STOP / emergency)."""
        self._cancel_requested = True

    def _abort_if_cancelled(
        self, results: list[StepResult], *, reason: str = "Emergency stop"
    ) -> bool:
        if not self._cancel_requested:
            return False
        self._abort_remaining(results, reason)
        return True

    def emergency_cleanup(self) -> None:
        self.request_cancel()
        self.gate.abort_all()
        self._log("EMERGENCY STOP — parking bench, breaking VISA if hung")
        self._progress("", "fail", "Emergency stop")
        if self._timeline:
            for e in self._timeline.entries:
                if e.status in ("running", "waiting"):
                    self._timeline.mark(
                        e.id, "fail", "Emergency stop", finish=True
                    )
            self._emit_timeline()
        instr = self._instr
        if instr is not None:
            for label, handle in (
                ("MSO", instr.scope),
                ("AWG", instr.gen),
                ("PSU", instr.psu),
            ):
                if handle is None:
                    continue
                try:
                    handle.clear()
                    handle.write("*CLS")
                except Exception as exc:
                    self._log(f"{label} clear: {exc}")
        try:
            self._safe_idle_for_operator(reason="emergency")
        except Exception as exc:
            self._log(f"safe idle emergency: {exc}")
        # Reopen MSO so a run thread stuck on :DISP:DATA? / query can error out
        if instr is not None and instr.scope is not None:
            try:
                instr.reopen_scope()
                self._log("MSO session reopened after emergency stop")
            except Exception as exc:
                self._log(f"MSO reopen: {exc}")
        with self._lock:
            self._busy = False

    def _safe_idle_for_operator(self, *, reason: str = "operator wait") -> None:
        """AWG OFF, then PSU OFF, then scope STOP -- before any operator Continue wait."""
        from generator_setup import park_generator_idle
        from psu_setup import power_off
        from scope_setup import park_scope_idle

        instr = self._instr
        if instr is None:
            return
        self._log(f"Safe idle ({reason}): AWG OFF, PSU OFF, then scope STOP")

        if instr.gen is not None:
            try:
                park_generator_idle(instr.gen)
            except Exception as exc:
                self._log(f"gen park idle: {exc}")

        if instr.psu is not None:
            try:
                try:
                    instr.psu.clear()
                except Exception:
                    pass
                try:
                    instr.psu.write("*CLS")
                except Exception:
                    pass
                power_off(instr.psu)
            except Exception as exc:
                self._log(f"psu off: {exc}")

        if instr.scope is not None:
            try:
                park_scope_idle(instr.scope, clear=True)
            except Exception as exc:
                self._log(f"scope idle: {exc}")

    def _ask_operator(self, **kwargs) -> bool:
        """Safe-idle bench, then block on Continue/Abort."""
        self._safe_idle_for_operator(
            reason=str(kwargs.get("kind") or kwargs.get("title") or "wait")
        )
        return self.gate.request(**kwargs)
