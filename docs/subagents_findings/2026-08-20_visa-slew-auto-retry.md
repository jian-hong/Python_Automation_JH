---
keywords: visa, VI_ERROR_SYSTEM_ERROR, slew, PSU, safe-idle, reopen_scope, auto-continue
main_idea: Slew DUT1 CHA Continue/Abort was MSO VISA death, not a DUT fail. *CLS is not enough; reopen MSO, retry once without the operator popup, and do not SAFE IDLE the PSU between those two attempts.
---

# VISA slew auto-retry (2026-08-20)

Operator saw: `Slew · DUT #1 CHA FAILED` / `VI_ERROR_SYSTEM_ERROR (-1073807360)` /
`Bench is SAFE IDLE (PSU/AWG OFF)` / Continue or Abort. PSU clicked ON then immediately OFF.

Why the PSU did that:

1. Slew `power_on_protected` turns DP832 ON.
2. MSO USB/VISA dies on a query or `:DISP:DATA?` leftover.
3. Slew `finally` + runner `_safe_idle_for_operator` turn PSU OFF for the Continue wait.

`recover_scope_session` (*CLS + drain) does not fix a dead handle. Next DUT repeats ON-fail-OFF.

Fix class (runner, not one test):

- `is_visa_poison` in `ate/drivers/mso5072.py`
- `Instruments.reopen_scope` drops and reopens MSO
- `_run_one` retries once after reopen; no SAFE IDLE between attempts
- VISA fail after retry auto-continues (no Continue popup). GND / Cnt=0 still asks.

Check: `python -m ate.drivers.check_slew_capture_run`
