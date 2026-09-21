# SCALE_WAVE_VERIFY_CHECKLIST 2026-09-21

SoT audit (box) 2026-09-21: no card/model mismatch for FAIL-bar controls. All 6 cards and all 6 models CONFIRMED. Attachment name kept. Use when promoting G00/G02/G04/G86/2G08/2G32 YAML. No invent.

## Must PASS (Path B Code)
- product_model / truth_table / isolation / vcc_grid / VOH / VOL / delta_icc_uA status CONFIRMED
- source_card = `docs/datasheet/<PART>_card_CONFIRMED.md` present
- G02 vcc_grid.kind TTL -- not G08 CMOS pair 0.65*VCC AND 0.15*VCC on the same row (G02 is 0.65/0.35)
- G86 VIL_max 0.20*VCC @ 1.65-1.95; VIH_min 0.65*VCC signed on that row
- RS2G08 / RS2G32 `recipe.dual_channel_continue` CHA then CHB; Path B logic_inputs A,B (ICC 2^2); do not skip rewire; unused channel hold VCC/GND
- oe none; IOZ OFF; ICCT ABSENT; delta_icc from signed `delta_icc_uA.offset_v` 0.6 (DeltaICC symbol -- no invent ICCT map / recipe.delta_offset_v)
- excel_plots.status CONFIRMED; series = enabled signed tests (vih/vil/icc/ii/voh/vol/delta_icc_vs_vcc)
- enabled_tests include voh/vol/delta_icc (tables CONFIRMED)
- G74/G123 PARKED out of SIM

## Must FAIL
- invent OE / IOZ / ICCT offset_v / one_input_V / recipe.delta_offset_v
- copy G08 CMOS pair 0.65/0.15 onto G02
- copy G08 VIL 0.15*VCC onto G86 @1.65-1.95
- skip CHA->CHB on 2G; rename Path B pins to 1A/1B (ICC 2^4)
- excel_plots.status UNCONFIRMED while VOH/VOL/delta_icc signed+enabled
- tick ioz with oe none
- extra `rs2g*.yaml` without a card
- invent MSL / retention MAX / G04 ROC VO MAX=5.5 as a normal operating limit / stable_eps_A

UNSURE / ABSENT stay fail-closed (not greenable). G00/2G CMOS 0.65/0.15 is their SoT (not a G02 swap).

## SoT audit vs FAIL-bar (box, 2026-09-21)

Scope: RS1G00, RS1G02, RS1G04, RS1G86, RS2G08, RS2G32. Result: 6/6 cards CONFIRMED; 6/6 models CONFIRMED and bound to the matching card.

### RS1G00
- Card `RS1G00_card_CONFIRMED.md`. Model CONFIRMED. runner `gate_nand2`.
- vcc_grid 4 rows, PSU_MSO, step 0.1 V: 1.65-1.95 VIH 0.65*VCC VIL 0.15*VCC; 2.3-2.7 1.7/0.3 V; 3.0-3.6 2.2/0.4 V; 4.5-5.5 0.7*VCC / 0.15*VCC.
- VOH/VOL six signed loads each (100 uA full-VCC-span + 4/8/16/24/32 mA).
- DeltaICC Full MAX 500 uA, VCC 3-5.5 V, one input at VCC-0.6 V. ICCT ABSENT. map_to delta_icc.
- No OE. IOZ OFF. stable_eps_A null. MSL UNSURE -- do not invent.

### RS1G02
- Card `RS1G02_card_CONFIRMED.md`. Model CONFIRMED. runner `gate_nor2`.
- TTL bands: 1.65-1.95 VIH 0.65*VCC VIL 0.35*VCC; 2.3-2.7 1.7/0.7 V; 3.0-3.6 VIH 2.0 V VIL 0.8 V; 4.5-5.5 0.7*VCC / 0.3*VCC. Do not substitute G08 CMOS.
- VOH/VOL six signed loads. DeltaICC 500 uA / VCC-0.6. ICCT ABSENT. IOZ OFF.
- Retention VCC MAX blank/UNSURE. stable_eps_A null.

### RS1G04
- Card `RS1G04_card_CONFIRMED.md`. Model CONFIRMED. runner `gate_inv`. N.C. is not OE.
- TTL-style same as G02 bands. VOH/VOL six signed loads. DeltaICC 500 uA / VCC-0.6. ICCT ABSENT. IOZ OFF.
- Retention MAX and ROC VO MAX=5.5 intent UNSURE -- do not promote ROC VO MAX into a normal operating limit. stable_eps_A null.

### RS1G86
- Card `RS1G86_card_CONFIRMED.md`. Model CONFIRMED. runner `gate_xor2`.
- 1.65-1.95 VIH 0.65*VCC VIL **0.20*VCC** (not G08 0.15*VCC). Then 2.3-2.7 1.7/0.3; 3.0-3.6 2.2/0.4; 4.5-5.5 0.7*VCC / 0.15*VCC.
- VOH/VOL six signed loads. DeltaICC 500 uA / VCC-0.6. ICCT ABSENT. IOZ OFF.
- Retention MAX UNSURE. stable_eps_A null.

### RS2G08
- Card `RS2G08_card_CONFIRMED.md`. Model CONFIRMED. runner `dual_and2`.
- CMOS bands like G00. VOH/VOL six signed loads. DeltaICC 500 uA / VCC-0.6. ICCT ABSENT. IOZ OFF (no OE/shared-enable).
- CHA then CHB Continue required. Path B `recipe.dual_channel_continue` + `channels: [CHA, CHB]`. Unused channel hold VCC/GND.
- II "A or B" applies to each of 1A/1B/2A/2B; do not invent different per-pin limits. Path B logic_inputs stay A,B (ICC 2^2).

### RS2G32
- Card `RS2G32_card_CONFIRMED.md`. Model CONFIRMED. runner `dual_or2`.
- Same CMOS bands, DeltaICC, ICCT ABSENT, IOZ OFF, CHA then CHB Continue as RS2G08.
- Isolation other=L track (OR). II each of 1A/1B/2A/2B; Path B A,B.

## Cross-part
- VCC grids: 4 signed rows on all six. G02/G04 TTL. G86 unique 0.20*VCC low-band VIL.
- Current: all six DeltaICC Full MAX 500 uA. ICCT absent -- do not invent.
- Dual-channel: RS2G08/RS2G32 CHA then CHB Continue.
- Open risks are documented UNSURE/fail-closed, not contradictions. No values from sibling parts.
