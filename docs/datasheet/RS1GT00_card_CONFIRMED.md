# RS1GT00_card_CONFIRMED -- GT-wave 2026-09-21

SoT for Code YAML `ate/config/parts/rs1gt00.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: gate_nand2. runner: gate_nand2.
- TTL NAND Y=NOT(A AND B): HH->L; LH->H; HL->H; LL->H.
- isolation other=H invert (do not copy G08 AND track).
- ICCT maps to delta_icc at one_input_V 3.4 (GT family). Do not invent 0.6.
- oe: none. IOZ OFF.
- pin names A B GND Y VCC. pin_drive AWG CH1=A CH2=B. Pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii/delta_icc).

## UNCONFIRMED HOLD -- do not invent
- vcc_grid TTL band numbers (kind TTL lock only)
- VOH loads, VOL loads, ICCT Full uA
- enable voh/vol/ioz: OFF
