# RS2G125_card_CONFIRMED -- GT-wave 2026-09-21

SoT for Code YAML `ate/config/parts/rs2g125.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: dual_buf. runner: dual_buf. output_type: three_state.
- recipe.dual_channel_continue: true. channels: [CHA, CHB]. Do not skip rewire.
- OE active L. IOZ when OE inactive H only (`recipe.ioz_when: oe_inactive`).
- IOZ ON @3.6V (`recipe.ioz_vcc_list: [3.6]`). uA Full UNSURE -- do not invent / do not copy G125 10uA.
- truth per channel: OE L A H->Y H; OE L A L->Y L; OE H -> Y Z.
- isolation A track with OE=L.
- pin names OE A GND Y VCC. AWG CH1=A CH2=OE. 8-pin numbers HOLD.
- excel_plots.status UNCONFIRMED (vih/vil/icc/ii/ioz -- no voh/vol).

## UNCONFIRMED HOLD -- do not invent
- vcc_grid bands (do not copy G125 VIL 0.3*VCC)
- VOH loads, VOL loads, IOZ Full uA, ICCT
- enable voh/vol/delta_icc: OFF
