# RS2G08_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs2g08.yaml`. Attached product_model CONFIRMED. Do not invent.

## CONFIRMED
- product_class: dual_and2. runner: dual_and2.
- recipe.dual_channel_continue: true. channels: [CHA, CHB]. Do not skip rewire.
- Path B logic_inputs A,B (ICC 2^2). Operator 8-pin SoT: 1=1A CHA, 2=1B CHA, 3=2Y CHB, 4=GND, 5=2A CHB, 6=2B CHB, 7=1Y CHA, 8=VCC.
- oe: none. IOZ OFF. ICCT name ABSENT (DeltaICC via delta_icc_uA.offset_v 0.6).
- truth AND per channel: HH->H; LH->L; HL->L; LL->L.
- isolation other=H track (Path B A/B).
- vcc_grid PSU_MSO CMOS: 0.65/0.15 @1.65-1.95; 1.7/0.3; 2.2/0.4; 0.7/0.15.
- VOH/VOL 6-load SoT. delta_icc_uA Full 500, vcc_min 3.0, offset_v 0.6.
- campaign package VSSOP8 (SoT package MSOP8 -- do not merge SKUs).
- enabled: input_threshold, icc, ii, voh, vol, delta_icc.
- excel_plots.status CONFIRMED.

## UNCONFIRMED HOLD -- do not invent
- stable_eps_A
- ICCT name / OE / IOZ
- extra rs2g*.yaml without a card: forbidden
