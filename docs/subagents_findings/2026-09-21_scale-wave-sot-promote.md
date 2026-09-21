# Scale-wave SoT promote (signed vcc_grid / VOH / VOL / DeltaICC)

Date: 2026-09-21
Keywords: path-b, DEMO DAY, scale-wave, rs1g00, rs1g02, rs1g04, rs1g86, rs2g08, rs2g32, signed loads, delta_icc_uA, ICCT ABSENT, G02 TTL, G86 VIL 0.20, CHA then CHB, SIM 24
**main_idea:** Promote rs1g00/02/04/86 + rs2g08/32 from attached SoT product_model YAMLs: CONFIRMED vcc_grid/VOH/VOL/delta_icc_uA, enable voh/vol/delta_icc, ICCT name ABSENT mapped via signed delta_icc_uA.offset_v 0.6. Keep Path B A/B + dual CHA then CHB (do not rename 1A/1B). G02 TTL 0.65/0.35 not CMOS pair. G86 VIL 0.20*VCC + VIH 0.65*VCC signed. `_icct_blob` reads CONFIRMED delta_icc_uA when ICCT ABSENT. `_grid_copies_g08_cmos` is same-row 0.65 AND 0.15 only. SIM stays 24 (17+7 GT-wave). PARKED G74/G123 out. HOLD GT125/126 unchanged. No invent OE/IOZ/ICCT.

## Cite
- distill: attached uploads rs1g00/02/04/86 + rs2g08/32 product_model yaml
- docs/SCALE_WAVE_VERIFY_CHECKLIST_2026-09-21.md
- docs/LIVE_MATRIX_17.md
