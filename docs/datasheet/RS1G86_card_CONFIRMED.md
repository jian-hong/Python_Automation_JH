# RS1G86_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g86.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: gate_xor2. runner: gate_xor2.
- oe: none. IOZ OFF. ICCT ABSENT.
- truth XOR: LL->L; HL->H; LH->H; HH->L.
- isolation dual: track other=L, invert other=H.
- vcc_grid CONFIRMED fragment: VIL_max 0.20*VCC @ 1.65-1.95 step 0.1. Not G08 0.15*VCC.
- pin names A B GND Y VCC. AWG CH1=A CH2=B. Pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii only).

## UNCONFIRMED HOLD -- do not invent
- VIH_min on the VIL fragment
- VOH loads, VOL loads, delta_icc_uA numbers
- enable voh/vol/delta_icc/ioz: OFF
