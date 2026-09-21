# RS1G86_card_CONFIRMED -- JH DEMO DAY 2026-09-21

SoT for Code YAML `ate/config/parts/rs1g86.yaml`. Attached product_model CONFIRMED. Do not invent.

## CONFIRMED
- product_class: gate_xor2. runner: gate_xor2.
- oe: none. IOZ OFF. ICCT name ABSENT (DeltaICC via delta_icc_uA.offset_v 0.6).
- truth XOR: LL->L; HL->H; LH->H; HH->L.
- isolation dual: track other=L, invert other=H.
- vcc_grid: VIL_max 0.20*VCC AND VIH_min 0.65*VCC @ 1.65-1.95. Not G08 0.15*VCC. Then 1.7/0.3; 2.2/0.4; 0.7/0.15.
- pin names A B GND Y VCC numbers 1-5. AWG CH1=A CH2=B.
- VOH/VOL 6-load SoT. delta_icc_uA Full 500, vcc_min 3.0, offset_v 0.6.
- enabled: input_threshold, icc, ii, voh, vol, delta_icc.
- excel_plots.status CONFIRMED.

## UNCONFIRMED HOLD -- do not invent
- stable_eps_A, retention MAX
- ICCT name / OE / IOZ
