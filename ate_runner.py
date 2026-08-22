"""Headless ATE runner — no GUI dependencies."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from configurations import VCC_LIST
from generator_setup import stop_output
from instruments import Instruments, find_instruments
from opa_tests import (
    DEFAULT_VOS_EXCEL_PATH,
    test_ac_gain_check,
    test_ac_vin_sweep,
    test_vos_sweep,
)
from psu_setup import power_off
from scope_setup import capture_scope_png

MYT = timezone(timedelta(hours=8))
REQUIRED_KEYS = ("MSO", "PSU", "AWG")
SCREENSHOT_DIR = Path(__file__).resolve().parent / "oscilloscope_screenshots"


class TestId(Enum):
    VOS_SWEEP = "vos_sweep"
    AC_GAIN_CHECK = "ac_gain_check"
    AC_VIN_SWEEP = "ac_vin_sweep"


class SmokeId(Enum):
    FIND_INSTRUMENTS = "find_instruments"
    RESET_ALL = "reset_all"
    STOP_OUTPUT = "stop_output"
    POWER_OFF = "power_off"


@dataclass
class TestParams:
    vcc: float = 5.0
    gain: float = 201.0
    freq_hz: float = 500.0
    amp_vpp: float = 0.004
    excel_path: str = ""
    sheet_name: str = ""
    reset_before_run: bool = False
    n_repeats: int = 3
    settle_s: Optional[float] = None


@dataclass
class PreflightReport:
    ok: bool
    mapping: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    success: bool
    test_id: Optional[TestId] = None
    smoke_id: Optional[SmokeId] = None
    summary: str = ""
    error: Optional[str] = None
    data: Optional[dict[str, Any]] = None


def resolve_excel_path(excel_path: str) -> str:
    """Use DEFAULT_VOS_EXCEL_PATH when excel_path is blank."""
    path = (excel_path or "").strip()
    return path if path else DEFAULT_VOS_EXCEL_PATH


def timestamped_sheet_name(prefix: str) -> str:
    # Excel sheet titles cannot contain : \ / ? * [ ]
    ts = datetime.now(MYT).strftime("%Y-%m-%d %H%M%S")
    return f"{prefix} {ts}"


def asrl_warnings(mapping: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    for key, resource in mapping.items():
        if resource.upper().startswith("ASRL"):
            warnings.append(
                f"ASRL warning: {key} uses serial resource {resource!r} — "
                "verify COM port, baud rate, and cable before running tests."
            )
    return warnings


def format_vos_summary(fit: dict[str, Any]) -> str:
    return (
        "VOS DC Sweep — linear fit\n"
        f"  slope     = {fit['slope']:.6f} V/V\n"
        f"  intercept = {fit['intercept']:.6f} V\n"
        f"  R²        = {fit['r_squared']:.6f}\n"
        f"  VOS       = {fit['vos_mV']:.4f} mV"
    )


def format_ac_gain_summary(data: dict[str, Any]) -> str:
    loop = "OK" if data.get("loop_ok") else "FAIL/CHECK"
    limit_mV = float(data.get("junction_vpp_limit", 0.001)) * 1000.0
    return (
        "AC Gain Check\n"
        f"  freq              = {data['freq_hz']:.1f} Hz\n"
        f"  amp commanded     = {data['amp_vpp_commanded'] * 1000:.3f} mVpp\n"
        f"  Vpp CH1 (OutB)    = {data['vpp_ch1']:.6f} V\n"
        f"  Vpp CH2 (junction)= {data['vpp_ch2']:.6f} V  [{loop}, "
        f"limit {limit_mV:.3f} mV]\n"
        f"  gain vs commanded = {data['gain_vs_commanded']:.4f} V/V\n"
        "  (CH1/CH2 is NOT used as gain — junction is virtual ground)"
    )


def format_ac_vin_summary(result: dict[str, Any]) -> str:
    repeats = result.get("repeats", [])
    lines = [f"AC Vin Sweep — {len(repeats)} repeat(s)"]
    for i, rep in enumerate(repeats, start=1):
        fit = rep["fit"]
        loop = "OK" if rep.get("loop_ok") else "FAIL/CHECK"
        lines.append(
            f"\n  Repeat {i}:\n"
            f"    slope     = {fit['slope']:.6f} V/V\n"
            f"    intercept = {fit['intercept']:.6f} V\n"
            f"    R²        = {fit['r_squared']:.6f}\n"
            f"    VOS       = {fit['vos_mV']:.4f} mV\n"
            f"    gain mean = {rep['gain_vs_commanded_mean']:.4f} V/V\n"
            f"    junction  = {rep['junction_vpp_max'] * 1000:.3f} mV max [{loop}]\n"
            f"    sheet     = {rep.get('sheet_name', '')}"
        )
    return "\n".join(lines)


def default_vcc() -> float:
    if VCC_LIST:
        return float(VCC_LIST[0])
    return 5.0


def ensure_screenshot_dir() -> Path:
    """Create and return the MSO5072 screenshot folder (for Open Screenshots)."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR


class ATERunner:
    """Thread-safe headless runner for bench tests and smoke actions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False
        self._cancel_requested = False
        self._instr: Optional[Instruments] = None
        self._mapping: dict[str, str] = {}

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    @property
    def session_open(self) -> bool:
        return self._instr is not None

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)

    def request_cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True

    def _ensure_not_busy(self) -> None:
        with self._lock:
            if self._busy:
                raise RuntimeError(
                    "ATERunner is busy — wait for the current operation to finish."
                )

    def _enter_busy(self) -> None:
        with self._lock:
            if self._busy:
                raise RuntimeError(
                    "ATERunner is busy — wait for the current operation to finish."
                )
            self._busy = True
            self._cancel_requested = False

    def _leave_busy(self) -> None:
        with self._lock:
            self._busy = False

    def discover(self) -> dict[str, str]:
        self._ensure_not_busy()
        self._enter_busy()
        try:
            print("=== PyVISA instrument discovery ===")
            mapping = find_instruments()
            self._mapping = dict(mapping)
            if mapping:
                print(f"Discovered: {mapping}")
                for warning in asrl_warnings(mapping):
                    print(f"WARNING: {warning}")
            else:
                print("No instruments found.")
            return dict(mapping)
        finally:
            self._leave_busy()

    def open_session(self, mapping: Optional[dict[str, str]] = None) -> None:
        self._ensure_not_busy()
        self._enter_busy()
        try:
            if self._instr is not None:
                print("Session already open — closing previous session first.")
                self._close_session_unlocked()

            if mapping is not None:
                self._mapping = dict(mapping)

            print("=== Opening instrument session ===")
            self._instr = Instruments()
            self._mapping = dict(self._instr.inst_map)
            for warning in asrl_warnings(self._mapping):
                print(f"WARNING: {warning}")
            print("Session open.")
        finally:
            self._leave_busy()

    def close_session(self, *, force: bool = False) -> None:
        if force:
            self._close_session_unlocked()
            return
        self._ensure_not_busy()
        self._enter_busy()
        try:
            self._close_session_unlocked()
        finally:
            self._leave_busy()

    def _close_session_unlocked(self) -> None:
        if self._instr is None:
            print("No open session.")
            return
        print("=== Closing instrument session ===")
        try:
            self._instr.close_all()
        except Exception as exc:
            print(f"Warning: close_all failed: {exc}")
        finally:
            self._instr = None
            print("Session closed.")

    def preflight(self, mapping: Optional[dict[str, str]] = None) -> PreflightReport:
        self._ensure_not_busy()
        self._enter_busy()
        try:
            use_mapping = dict(mapping if mapping is not None else self._mapping)
            if not use_mapping:
                use_mapping = find_instruments()
                self._mapping = dict(use_mapping)

            warnings = asrl_warnings(use_mapping)
            missing = [k for k in REQUIRED_KEYS if k not in use_mapping]
            errors: list[str] = []
            if not use_mapping:
                errors.append("No instruments discovered on USB/VISA.")
            if missing:
                errors.append(f"Missing required instruments: {missing}")

            ok = bool(use_mapping) and not missing
            report = PreflightReport(
                ok=ok,
                mapping=use_mapping,
                warnings=warnings,
                errors=errors,
                missing=missing,
            )

            print("=== Preflight ===")
            print(f"  OK: {ok}")
            print(f"  Mapping: {use_mapping}")
            for warning in warnings:
                print(f"  WARNING: {warning}")
            for error in errors:
                print(f"  ERROR: {error}")
            return report
        finally:
            self._leave_busy()

    def run_test(self, test_id: TestId, params: TestParams) -> RunResult:
        self._ensure_not_busy()
        self._enter_busy()
        try:
            if self._instr is None:
                return RunResult(
                    success=False,
                    test_id=test_id,
                    error="No open session — use Open Session first.",
                )

            excel_path = resolve_excel_path(params.excel_path)

            if params.reset_before_run:
                print("=== Reset all instruments (pre-run) ===")
                self._instr.reset_all()

            if test_id is TestId.VOS_SWEEP:
                sheet_name = params.sheet_name or timestamped_sheet_name("vos sweep")
                print(f"=== VOS DC sweep — sheet '{sheet_name}' ===")
                result = test_vos_sweep(
                    self._instr,
                    vcc=params.vcc,
                    gain=params.gain,
                    excel_path=excel_path,
                    sheet_name=sheet_name,
                )
                summary = format_vos_summary(result["fit"])
                print(summary)
                return RunResult(
                    success=True,
                    test_id=test_id,
                    summary=summary,
                    data=result,
                )

            if test_id is TestId.AC_GAIN_CHECK:
                sheet_name = params.sheet_name or timestamped_sheet_name("ac gain check")
                print(f"=== AC gain check — sheet '{sheet_name}' ===")
                result = test_ac_gain_check(
                    self._instr,
                    vcc=params.vcc,
                    freq_hz=params.freq_hz,
                    amp_vpp=params.amp_vpp,
                    excel_path=excel_path,
                    sheet_name=sheet_name,
                    gain_nominal=params.gain,
                )
                summary = format_ac_gain_summary(result)
                print(summary)
                return RunResult(
                    success=True,
                    test_id=test_id,
                    summary=summary,
                    data=result,
                )

            if test_id is TestId.AC_VIN_SWEEP:
                print(f"=== AC Vin sweep — {params.n_repeats} repeat(s) ===")
                kwargs = dict(
                    vcc=params.vcc,
                    gain=params.gain,
                    freq_hz=params.freq_hz,
                    amp_vpp=params.amp_vpp,
                    excel_path=excel_path,
                    n_repeats=params.n_repeats,
                )
                if params.settle_s is not None:
                    kwargs["settle_s"] = params.settle_s
                result = test_ac_vin_sweep(self._instr, **kwargs)
                summary = format_ac_vin_summary(result)
                print(summary)
                return RunResult(
                    success=True,
                    test_id=test_id,
                    summary=summary,
                    data=result,
                )

            return RunResult(
                success=False,
                test_id=test_id,
                error=f"Unknown test: {test_id}",
            )
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"Test failed: {msg}")
            return RunResult(success=False, test_id=test_id, error=msg)
        finally:
            self._leave_busy()

    def run_smoke(self, smoke_id: SmokeId) -> RunResult:
        self._ensure_not_busy()
        self._enter_busy()
        try:
            if smoke_id is SmokeId.FIND_INSTRUMENTS:
                print("=== PyVISA instrument discovery ===")
                mapping = find_instruments()
                self._mapping = dict(mapping)
                if mapping:
                    print(f"Discovered: {mapping}")
                    for warning in asrl_warnings(mapping):
                        print(f"WARNING: {warning}")
                else:
                    print("No instruments found.")
                summary = f"Found {len(mapping)} instrument(s): {mapping}"
                return RunResult(
                    success=bool(mapping),
                    smoke_id=smoke_id,
                    summary=summary,
                    data={"mapping": mapping},
                )

            if self._instr is None and smoke_id is not SmokeId.FIND_INSTRUMENTS:
                return RunResult(
                    success=False,
                    smoke_id=smoke_id,
                    error="No open session — use Open Session first.",
                )

            if smoke_id is SmokeId.RESET_ALL:
                print("=== Smoke: reset all instruments ===")
                self._instr.reset_all()
                return RunResult(
                    success=True,
                    smoke_id=smoke_id,
                    summary="All instruments sent *RST.",
                )

            if smoke_id is SmokeId.STOP_OUTPUT:
                print("=== Smoke: stop generator output ===")
                if self._instr.gen is None:
                    return RunResult(
                        success=False,
                        smoke_id=smoke_id,
                        error="AWG not connected.",
                    )
                stop_output(self._instr.gen)
                return RunResult(
                    success=True,
                    smoke_id=smoke_id,
                    summary="Generator outputs OFF.",
                )

            if smoke_id is SmokeId.POWER_OFF:
                print("=== Smoke: PSU power off ===")
                if self._instr.psu is None:
                    return RunResult(
                        success=False,
                        smoke_id=smoke_id,
                        error="PSU (DP832) not connected.",
                    )
                power_off(self._instr.psu)
                return RunResult(
                    success=True,
                    smoke_id=smoke_id,
                    summary="PSU outputs OFF.",
                )

            return RunResult(
                success=False,
                smoke_id=smoke_id,
                error=f"Unknown smoke action: {smoke_id}",
            )
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"Smoke action failed: {msg}")
            return RunResult(success=False, smoke_id=smoke_id, error=msg)
        finally:
            self._leave_busy()

    def capture_screenshot(self, prefix: str = "manual") -> str:
        """Capture RIGOL MSO5072 screen as JPEG via open session (:DISP:DATA?).

        Reuses ``self._instr.scope`` — does not open a second Instruments().
        Saves ``.jpg`` (PNG from scope auto-converted) for Excel insert.
        Returns the saved file path string.
        """
        if self._instr is None:
            raise RuntimeError("Open a session first.")
        if self._instr.scope is None:
            raise RuntimeError("MSO5072 not in session — reconnect scope and Open Session again.")

        self._ensure_not_busy()
        self._enter_busy()
        try:
            out_dir = ensure_screenshot_dir()
            ts = datetime.now(MYT).strftime("%Y-%m-%d_%H%M%S")
            path = out_dir / f"{prefix}_{ts}.jpg"
            print(f"=== MSO5072 screenshot (JPEG) → {path} ===")
            saved = capture_scope_png(self._instr.scope, path)
            print(f"Saved: {saved}")
            return saved
        finally:
            self._leave_busy()

    def emergency_cleanup(self) -> None:
        """Best-effort shutdown — safe to call from GUI close handler."""
        print("=== Emergency cleanup ===")
        instr = self._instr
        if instr is not None:
            if instr.gen is not None:
                try:
                    stop_output(instr.gen)
                except Exception as exc:
                    print(f"Warning: generator stop failed: {exc}")
            if instr.psu is not None:
                try:
                    power_off(instr.psu)
                except Exception as exc:
                    print(f"Warning: PSU off failed: {exc}")
        print("Emergency cleanup complete.")
