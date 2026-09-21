# RS1G02_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g02.yaml`. Attached product_model CONFIRMED. Do not invent.

## CONFIRMED
- product_class: gate_nor2. runner: gate_nor2.
- oe: none. IOZ OFF. ICCT name ABSENT (DeltaICC via delta_icc_uA.offset_v 0.6).
- truth NOR Y=NOT(A OR B): LL->H; HL->L; LH->L; HH->L.
- isolation other=L invert (do not copy G32 OR track).
- vcc_grid.kind: TTL. Bands 0.65/0.35 @1.65-1.95; 1.7/0.7; 2.0/0.8; 0.7/0.3*VCC. Not G08 CMOS 0.65/0.15 pair.
- pin names A B GND Y VCC numbers 1-5. AWG CH1=A CH2=B.
- VOH/VOL 6-load SoT. delta_icc_uA Full 500, vcc_min 3.0, offset_v 0.6.
- enabled: input_threshold, icc, ii, voh, vol, delta_icc.
- excel_plots.status CONFIRMED.

## UNCONFIRMED HOLD -- do not invent
- stable_eps_A, retention MAX
- ICCT name / OE / IOZ
