# RS1G00_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g00.yaml`. Attached product_model CONFIRMED. Do not invent.

## CONFIRMED
- product_class: gate_nand2. runner: gate_nand2.
- oe: none. IOZ OFF. ICCT name ABSENT (DeltaICC via delta_icc_uA.offset_v 0.6).
- truth NAND Y=NOT(A AND B): HH->L; LH->H; HL->H; LL->H.
- isolation other=H invert (do not copy G08 AND track).
- pin names A B GND Y VCC numbers 1-5. pin_drive AWG CH1=A CH2=B.
- vcc_grid PSU_MSO CMOS: 0.65/0.15 @1.65-1.95; 1.7/0.3; 2.2/0.4; 0.7/0.15.
- VOH/VOL 6-load SoT. delta_icc_uA Full 500, vcc_min 3.0, offset_v 0.6, map_to delta_icc.
- enabled: input_threshold, icc, ii, voh, vol, delta_icc.
- excel_plots.status CONFIRMED (vih/vil/icc/ii/voh/vol/delta_icc_vs_vcc).

## UNCONFIRMED HOLD -- do not invent
- stable_eps_A, MSL
- ICCT name / OE / IOZ
