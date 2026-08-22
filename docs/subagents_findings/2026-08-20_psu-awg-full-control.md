---
keywords: psu, awg, safe-idle, power_on_protected, park_generator_idle, slew, settling
main_idea: PSU/AWG stay ON for the whole Slew/Settling measurement including VISA retry. Only SAFE IDLE turns them off, in order AWG then PSU then scope. Bring-up must not pulse OFF; AWG park must not APPL.
---

# PSU / AWG full control (2026-08-20)

Operator saw DP832 click ON then immediately OFF, and AWG flash during idle.

Causes:

1. `power_on_protected` wrote `:OUTP OFF` before ON.
2. Slew/Settling `finally` called `power_off` + `stop_output`, so VISA retry found rails dead.
3. `park_generator_idle` used `:APPL:SIN`, which on DG800 turns the AC output ON then OFF.
4. SAFE IDLE parked the scope before PSU off, so a dead MSO delayed cutting rails.

Fix:

- Bring-up: set V/I/protect, then ON, readback.
- Slew/Settling finally: scope measure clear only.
- SAFE IDLE: AWG OFF, PSU OFF (readback), then scope STOP.
- AWG park: FUNC/FREQ/VOLT, never APPL.

Check: `python -m ate.drivers.check_slew_capture_run`
