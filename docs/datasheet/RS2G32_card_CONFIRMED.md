# RS2G32_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs2g32.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: dual_or2. runner: dual_or2.
- recipe.dual_channel_continue: true. channels: [CHA, CHB]. Do not skip rewire.
- oe: none. IOZ OFF. ICCT ABSENT.
- truth OR per channel: HH->H; LH->H; HL->H; LL->L.
- isolation other=L track.
- pin names A B GND Y VCC. AWG CH1=A CH2=B per channel. 8-pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii only).

## UNCONFIRMED HOLD -- do not invent
- vcc_grid bands (do not copy G08 CMOS)
- VOH loads, VOL loads, delta_icc_uA numbers, pin numbers
- enable voh/vol/delta_icc/ioz: OFF
- extra rs2g*.yaml without a card: forbidden
