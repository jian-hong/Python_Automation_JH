# RS1G02_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g02.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: gate_nor2. runner: gate_nor2.
- oe: none. IOZ OFF. ICCT ABSENT.
- truth NOR Y=NOT(A OR B): LL->H; HL->L; LH->L; HH->L.
- isolation other=L invert (do not copy G32 OR track).
- vcc_grid.kind: TTL (not G08 CMOS 0.65*VCC / 0.15*VCC). Band numbers HOLD.
- pin names A B GND Y VCC. AWG CH1=A CH2=B. Pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii only).

## UNCONFIRMED HOLD -- do not invent
- TTL VIH/VIL band numbers
- VOH loads, VOL loads, delta_icc_uA numbers
- enable voh/vol/delta_icc/ioz: OFF
