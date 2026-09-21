# RS1G04_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g04.yaml`. Attached product_model CONFIRMED. Do not invent.

## CONFIRMED
- product_class: gate_inv. runner: gate_inv.
- n=1 Y=NOT A. NC role=nc number 1 -- NC is not OE. IOZ OFF. ICCT name ABSENT.
- truth: A H->Y L; A L->Y H. isolation A invert.
- pin names NC A GND Y VCC numbers 1-5. AWG CH1=A.
- vcc_grid TTL-style: 0.65/0.35 @1.65-1.95; 1.7/0.7; 2.0/0.8; 0.7/0.3*VCC.
- VOH/VOL 6-load SoT. delta_icc_uA Full 500, vcc_min 3.0, offset_v 0.6.
- enabled: input_threshold, icc, ii, voh, vol, delta_icc.
- excel_plots.status CONFIRMED.

## UNCONFIRMED HOLD -- do not invent
- stable_eps_A, retention MAX, VO MAX=5.5 intent
- ICCT name / OE / IOZ
