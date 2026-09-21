# RS2GT08_card_CONFIRMED -- GT-wave 2026-09-21

SoT for Code YAML `ate/config/parts/rs2gt08.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: dual_and2. runner: dual_and2.
- recipe.dual_channel_continue: true. channels: [CHA, CHB]. Do not skip rewire.
- TTL AND per channel: HH->H; LH->L; HL->L; LL->L.
- isolation other=H track.
- vcc_grid.kind: TTL (not G08 CMOS). Band numbers HOLD.
- oe: none. IOZ OFF. ICCT ABSENT (do not invent 0.6).
- pin names A B GND Y VCC. AWG CH1=A CH2=B per channel. 8-pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii only).

## UNCONFIRMED HOLD -- do not invent
- TTL VIH/VIL band numbers
- VOH loads, VOL loads, delta_icc_uA numbers, pin numbers
- enable voh/vol/delta_icc/ioz: OFF
