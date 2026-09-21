# SCALE_WAVE_VERIFY_CHECKLIST 2026-09-21

Use when promoting G00/G02/G04/G86/2G08/2G32 YAML from CONFIRMED cards. No invent. Attachment name kept.

## Must PASS
- product_model / truth_table / isolation status CONFIRMED
- source_card = `docs/datasheet/<PART>_card_CONFIRMED.md` present
- G02 vcc_grid.kind TTL -- not G08 CMOS 0.65*VCC / 0.15*VCC
- G86 VIL_max 0.20*VCC @ 1.65-1.95; VIH HOLD (no VIH_min on that fragment)
- RS2G08 / RS2G32 `recipe.dual_channel_continue` CHA then CHB; do not skip rewire
- oe none; IOZ OFF; ICCT ABSENT; delta_icc only from `delta_icc_uA` (no invent ICCT map)
- excel_plots.status UNCONFIRMED; series = enabled tests only (vih/vil/icc/ii)
- enabled_tests must not include voh/vol/ioz/delta_icc until tables CONFIRMED
- G74/G123 PARKED out of SIM

## Must FAIL
- invent OE / IOZ / ICCT offset_v / one_input_V
- copy G08 CMOS onto G02 / G00
- copy G08 VIL 0.15*VCC onto G86
- skip CHA->CHB on 2G
- excel_plots.status CONFIRMED while VOH/VOL unsigned
- tick voh/vol/delta_icc with UNCONFIRMED tables
- extra `rs2g*.yaml` without a card

UNSURE / ABSENT / empty ranges stay fail-closed (not greenable).
