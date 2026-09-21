# RS2G00_card_CONFIRMED -- GT-wave 2026-09-21

SoT for Code YAML `ate/config/parts/rs2g00.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: dual_nand2. runner: dual_nand2.
- recipe.dual_channel_continue: true. channels: [CHA, CHB]. Do not skip rewire.
- oe: none. IOZ OFF. ICCT ABSENT.
- truth NAND per channel: HH->L; LH->H; HL->H; LL->H.
- isolation other=H invert.
- pin names A B GND Y VCC. AWG CH1=A CH2=B per channel. 8-pin numbers HOLD.
- excel_plots.status UNCONFIRMED (enabled series vih/vil/icc/ii only).

## UNCONFIRMED HOLD -- do not invent
- vcc_grid bands (do not copy G08 CMOS)
- VOH loads, VOL loads, delta_icc_uA numbers, pin numbers
- enable voh/vol/delta_icc/ioz: OFF
