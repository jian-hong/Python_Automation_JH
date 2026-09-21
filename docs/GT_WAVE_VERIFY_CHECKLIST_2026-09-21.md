# GT_WAVE_VERIFY_CHECKLIST 2026-09-21

Use when binding GT-wave YAML from CONFIRMED cards. No invent.

## Must PASS
- 7 CONFIRMED in SIM 24: rs1gt00, rs1gt02, rs1gt04, rs1gt14, rs2g00, rs2g125, rs2gt08
- source_card = `docs/datasheet/<PART>_card_CONFIRMED.md` present
- GT00 TTL NAND ICCT->dICC @3.4 (not 0.6); delta_icc enabled
- GT02 TTL NOR -- not G08 CMOS
- GT04 INV n=1; NC not OE
- GT14 Schmitt VT+/- ONLY -- tick vth; no VIH/VIL keys
- 2G00 dual NAND CHA then CHB
- 2G125 dual buf OE-L; IOZ ON @3.6V UNSURE; CHA then CHB
- 2GT08 dual TTL AND CHA then CHB; ICCT ABSENT
- HOLD stubs rs1gt125 / rs1gt126 process-only (not SIM 24)
- G74/G123 PARKED out of SIM
- excel_plots.status UNCONFIRMED unless every enabled series is signed

## Must FAIL
- invent VIH on GT14
- invent IOZ on GT125/126 (OE present, IOZ ABSENT)
- invent OE / ICCT 0.6
- G02 CMOS swap (0.65/0.15) onto TTL GT parts
- skip CHA->CHB on 2G00 / 2G125 / 2GT08
- tick voh/vol with UNCONFIRMED tables
- extra `rs2g*.yaml` without a card

UNSURE / ABSENT / empty ranges stay fail-closed (not greenable).
