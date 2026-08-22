"""Fails if screenshot capture parks STOP (kills slew/ORT/settling shot 2+).

Run: python -m ate.drivers.check_slew_capture_run
"""
from __future__ import annotations

import inspect

from ate.core.runner import ATECore
from ate.drivers.mso5072 import (
    apply_scope_manual,
    is_visa_poison,
    setup_settling_photo,
    wait_slew_statistics,
)
from ate.instruments.session import Instruments
from ate.tests.opa import settling as settling_mod
from ate.tests.opa import slew as slew_mod
from ate.tests.opa.slew import SLEW_FIXED_STEPS
from generator_setup import park_generator_idle, setup_square
from psu_setup import power_off, power_on_protected
from scope_setup import capture_scope_png


class _FakeScope:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.timeout = 1000
        self._scale = {"1": "0.2", "2": "0.2"}
        self._offs = {"1": "0.208", "2": "-0.208"}

    def write(self, cmd: str) -> None:
        self.writes.append(str(cmd))
        text = str(cmd)
        for ch in ("1", "2"):
            if f":CHAN{ch}:SCALe " in text:
                self._scale[ch] = text.split()[-1]
            if f":CHAN{ch}:OFFS " in text:
                self._offs[ch] = text.split()[-1]

    def query(self, cmd: str) -> str:
        text = str(cmd)
        for ch in ("1", "2"):
            if f":CHAN{ch}:SCALe?" in text:
                return self._scale[ch]
            if f":CHAN{ch}:OFFS?" in text:
                return self._offs[ch]
        return "120"


class _FakePsu:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.states = {"1": "OFF", "2": "OFF", "3": "OFF"}

    def write(self, cmd: str) -> None:
        self.writes.append(str(cmd))
        text = str(cmd).upper().replace(" ", "")
        for ch in ("1", "2", "3"):
            if f":OUTPCH{ch},ON" in text:
                self.states[ch] = "ON"
            elif f":OUTPCH{ch},OFF" in text:
                self.states[ch] = "OFF"

    def query(self, cmd: str) -> str:
        text = str(cmd).upper().replace(" ", "")
        for ch in ("1", "2", "3"):
            if f":OUTP?CH{ch}" in text:
                return self.states[ch]
        return "OFF"


class _FakeGen:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.out = {str(c): "OFF" for c in range(1, 5)}

    def write(self, cmd: str) -> None:
        self.writes.append(str(cmd))
        text = str(cmd).upper().replace(" ", "")
        for ch in ("1", "2", "3", "4"):
            if f":OUTP{ch}ON" in text:
                self.out[ch] = "ON"
            elif f":OUTP{ch}OFF" in text:
                self.out[ch] = "OFF"

    def query(self, cmd: str) -> str:
        text = str(cmd).upper().replace(" ", "")
        for ch in ("1", "2", "3", "4"):
            if f":OUTP{ch}?" in text:
                return self.out[ch]
        return "OFF"

    def clear(self) -> None:
        return None


def main() -> int:
    src = inspect.getsource(capture_scope_png)
    if "park_scope_idle(" in src:
        raise AssertionError(
            "capture_scope_png must not park STOP after JPEG "
            "(slew POS_2V then shows Cnt=0 / ****)"
        )
    if "recover_scope_session" not in src or "run=True" not in src:
        raise AssertionError(
            "capture_scope_png must recover_scope_session(..., run=True) after :DISP:DATA?"
        )

    scope = _FakeScope()
    apply_scope_manual(
        scope,
        {
            "timebase": 200e-9,
            "trig_level": 0,
            "ch1_scale": 0.2,
            "ch1_offset": 0.208,
            "ch2_scale": 0.2,
            "ch2_offset": -0.208,
        },
    )
    if not any(w.strip() == ":RUN" for w in scope.writes):
        raise AssertionError("apply_scope_manual must :RUN after locking scales")
    joined = " ".join(scope.writes)
    if ":CHAN1:DISP ON" not in joined or ":CHAN2:DISP ON" not in joined:
        raise AssertionError("apply_scope_manual must turn CHAN1/CHAN2 display on")
    if ":CHAN1:COUP DC" not in joined or ":CHAN2:COUP DC" not in joined:
        raise AssertionError("apply_scope_manual must force DC coupling (GBW leaves AC)")
    if ":CHAN2:SCALe 0.2" not in joined:
        raise AssertionError("apply_scope_manual must write CHAN2 200 mV (not leftover 100 mV)")

    scope2 = _FakeScope()
    wait_slew_statistics(scope2, "PSLewrate", min_count=80, timeout_s=0.2, settle_s=0)
    if not any(w.strip() == ":RUN" for w in scope2.writes):
        raise AssertionError("wait_slew_statistics must :RUN before accumulating")

    ids = [s["id"] for s in SLEW_FIXED_STEPS]
    if ids != ["pos_1v", "neg_1v", "pos_2v", "neg_2v"]:
        raise AssertionError(f"slew must be POS/NEG @ 1V and 2V, got {ids}")

    scope3 = _FakeScope()
    setup_settling_photo(scope3, ax_px=350, bx_px=675)
    joined3 = " ".join(scope3.writes)
    if ":CURSor:MODE MANual" not in joined3 or "VMAX,CHAN2" not in joined3:
        raise AssertionError("settling photo must set TIME cursors + Vpp1/Vmax2")

    visa_msg = "VI_ERROR_SYSTEM_ERROR (-1073807360): Unknown system error"
    if not is_visa_poison(visa_msg):
        raise AssertionError("is_visa_poison must match VI_ERROR_SYSTEM_ERROR")
    if is_visa_poison("probe on GND / wrong channel / AWG off"):
        raise AssertionError("GND/Cnt=0 must still ask the operator")

    run_one = inspect.getsource(ATECore._run_one)
    if "is_visa_poison" not in run_one or "range(2)" not in run_one:
        raise AssertionError("_run_one must retry once on VISA poison")
    if "_reopen_mso_after_visa" not in run_one:
        raise AssertionError("_run_one retry must reopen MSO, not only *CLS")
    if "_safe_idle_for_operator" in run_one:
        raise AssertionError(
            "_run_one must not SAFE IDLE (PSU OFF) between VISA retries"
        )

    seq = inspect.getsource(ATECore.run_sequence)
    if "auto-continue next unit" not in seq:
        raise AssertionError("VISA fail after retry must skip Continue/Abort popup")

    reopen = inspect.getsource(Instruments.reopen_scope)
    if "open_resource" not in reopen:
        raise AssertionError("Instruments.reopen_scope must open a fresh MSO handle")

    psu_on_src = inspect.getsource(power_on_protected)
    if ",OFF" in psu_on_src:
        raise AssertionError("power_on_protected must not pulse OUTP OFF before ON")
    psu = _FakePsu()
    power_on_protected(psu, 1, 2.5, 0.1)
    power_on_protected(psu, 2, 2.5, 0.1)
    if any(",OFF" in w.upper() for w in psu.writes):
        raise AssertionError("bring-up wrote OUTP OFF (PSU click-off)")
    if psu.states["1"] != "ON" or psu.states["2"] != "ON":
        raise AssertionError("power_on_protected must leave CH1+CH2 ON")
    power_off(psu)
    if any(psu.states[c] != "OFF" for c in ("1", "2", "3")):
        raise AssertionError("power_off must leave all PSU channels OFF")

    gen = _FakeGen()
    setup_square(gen, 1, 1000, 1.0, 0)
    if gen.out["1"] != "ON":
        raise AssertionError("setup_square must turn AWG CH1 ON")
    parked = _FakeGen()
    park_generator_idle(parked)
    if any(":APPL" in w.upper() for w in parked.writes):
        raise AssertionError("park_generator_idle must not APPL (DG800 APPL turns AC ON)")
    if parked.out["1"] != "OFF":
        raise AssertionError("park_generator_idle must leave AWG CH1 OFF")

    for name, fn in (("slew", slew_mod._run), ("settling", settling_mod._run)):
        finally_part = inspect.getsource(fn).split("finally:", 1)[-1]
        if "power_off" in finally_part or "stop_output" in finally_part:
            raise AssertionError(
                f"{name} finally must not kill PSU/AWG (runner SAFE IDLE owns off)"
            )

    idle = inspect.getsource(ATECore._safe_idle_for_operator)
    gen_i = idle.rfind("park_generator_idle(")
    psu_i = idle.rfind("power_off(")
    scope_i = idle.rfind("park_scope_idle(")
    if min(gen_i, psu_i, scope_i) < 0 or not (gen_i < psu_i < scope_i):
        raise AssertionError("SAFE IDLE must be AWG OFF, then PSU OFF, then scope STOP")

    print("ok: capture leaves RUN; slew 4 edges; settling cursors; visa retry; PSU/AWG control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
