# RS1GT14_card_CONFIRMED -- GT-wave 2026-09-21

SoT for Code YAML `ate/config/parts/rs1gt14.yaml`. Reconstruct from grounded function rows (models/attachments missing). Do not invent.

## CONFIRMED
- product_class: gate_inv. runner: gate_inv. schmitt: true.
- n=1 Y=NOT A. Tick vth (VT+/-). Do NOT invent VIH/VIL keys or bands.
- vcc_grid.kind: schmitt_VT. VT+/- numbers HOLD -- do not copy G14 VT table.
- NC role=nc -- NC is not OE. IOZ OFF. ICCT ABSENT (do not copy G14 offset_v 0.6).
- pin names NC A GND Y VCC. AWG CH1=A. Pin numbers HOLD.
- excel_plots.status UNCONFIRMED (vtplus/vtminus/dvt/icc/ii -- no vih/vil).

## UNCONFIRMED HOLD -- do not invent
- VT+/VT-/dVT numbers
- VIH/VIL keys (FORBIDDEN -- FAIL if present)
- VOH loads, VOL loads, delta_icc_uA numbers
- enable input_threshold / voh / vol / delta_icc / ioz: OFF
