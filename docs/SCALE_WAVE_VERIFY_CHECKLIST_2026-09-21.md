# SCALE_WAVE_VERIFY_CHECKLIST 2026-09-21

Use when promoting G00/G02/G04/G86/2G08/2G32 YAML from CONFIRMED SoT models. No invent. Attachment name kept.

## Must PASS
- product_model / truth_table / isolation / vcc_grid / VOH / VOL / delta_icc_uA status CONFIRMED
- source_card = `docs/datasheet/<PART>_card_CONFIRMED.md` present
- G02 vcc_grid.kind TTL -- not G08 CMOS pair 0.65*VCC AND 0.15*VCC on the same row (G02 is 0.65/0.35)
- G86 VIL_max 0.20*VCC @ 1.65-1.95; VIH_min 0.65*VCC signed on that row
- RS2G08 / RS2G32 `recipe.dual_channel_continue` CHA then CHB; Path B logic_inputs A,B (ICC 2^2); do not skip rewire
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

UNSURE / ABSENT stay fail-closed (not greenable). G00/2G CMOS 0.65/0.15 is their SoT (not a G02 swap).
