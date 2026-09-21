# RS1G00_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g00.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: gate_nand2. runner: gate_nand2.
- oe: none. IOZ OFF. ICCT ABSENT (not a delta_icc map).
- truth NAND Y=NOT(A AND B): HH->L; LH->H; HL->H; LL->H.
- isolation other=H invert (do not copy G08 AND track).
- pin names A B GND Y VCC. pin_drive AWG CH1=A CH2=B. Pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii only).

## UNCONFIRMED HOLD -- do not invent
- vcc_grid bands (do not copy G08 CMOS 0.65/0.15)
- VOH loads, VOL loads, delta_icc_uA numbers
- enable voh/vol/delta_icc/ioz: OFF
