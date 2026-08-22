---
keywords: slew, screenshot, park_scope_idle, STOP, Cnt=0, GND, AC-coupling, settling, GBW
main_idea: Today's empty SlewRate POS_2V shot was GND on the probe plus capture_scope_png parking STOP after JPEG so shots 2-4 never re-RUN.
---

# Slew empty screenshot (2026-08-20)

Today `SlewRate_1_POS_2V_CHA` (15:43): STOP, Cnt 0, ****, CH1 noise blip, CH2 flat.
July 31 `SlewRate_1_POS_2V_CHB` (11:47): T'D, Cnt 179, 2 V step + ramp, ~4 MV/s.

Two causes, both real:

1. Operator: CHA probe on GND (no input step, no output slew).
2. Code: `capture_scope_png` called `park_scope_idle` after every `:DISP:DATA?`. Slew is 4 JPEGs. Shot 1 might live; POS_2V is shot 3, already STOP, then `MEASure:CLEar` -> Cnt=0. `apply_scope_manual` had no `:RUN`.

Fix class (not one test):

- `capture_scope_png` -> `recover_scope_session(..., run=True)`. Runner still parks after the test.
- `apply_scope_manual` and `wait_slew_statistics` send `:RUN`.
- `wait_slew_statistics` raises if Cnt still 0 (GND / AWG off fails loud, no fake JPEG).

Screenshot adjustment (vs LabAutomation `test_sr` + goldens):

- Original 14.7: 2 Vpp only, AUToscale, 500 mV, CH1 -20 mV, delay 400 ns, MOFF before photo.
- ATE goldens (31 Jul POS_1V): 200 mV +208 / CH2 200 mV -208, delay 201 ns. Keep those numbers.
- Bug: POS_1V often left CH2 at leftover 100 mV (7 Aug + today). `_force_chan` write+readback.
- Measure:ITEM opens the right menu; MOFF must run AFTER stats setup, immediately before JPEG.
- CH1 Vpp < 40% of target -> fail (GND), do not keep four junk JPEGs.
- 20 Aug 16:06 settling: CH1 2 V step OK, CH2 flat. GBW leaves `:CHAN2:COUPling AC`; slew/settling never restored DC. `apply_scope_manual` now forces DC. Slew DUT1 also died with `VI_ERROR_SYSTEM_ERROR`.

Check: `python -m ate.drivers.check_slew_capture_run`
---
