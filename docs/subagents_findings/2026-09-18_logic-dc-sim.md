# Logic Reference Path B SIM + RS1G123/RS1G74 stubs

Date: 2026-09-18
Keywords: path-b, logic-dc, sim, check_logic_dc_sim, rs1g123, rs1g74, sequential, UNCONFIRMED, visa-free, NON_TIGHT, G07 VOH N_A, VOL NOT_RUN

## main_idea

Visa-free Path B SIM (`python -m ate.core.check_logic_dc_sim`) runs the applicable DC catalog on every Logic Reference `product_model` SKU. Overlay one VCC; `stable_eps_A` stays null (NON_TIGHT). Sequential is not combinational 2^n. Open-drain G07 VOH SKIP. RS1G123 / RS1G74 are UNCONFIRMED sequential stubs from extract pins + VCC range only -- glyph function table / 100uA formula stay gaps. Not a bench green / not Verify PASS.

## traps

- Do not add 123/74 to `_DRAFT_SCAFFOLD_SKUS` (that gate requires CONFIRMED).
- 123 extract names Schmitt on A/B but VT+/- numbers are missing -- `schmitt: false` until card (`_physics_fail_bars_ok`).
- 74 ICCT VCC-0.6 on extract is unsigned -- do not map `offset_v` / enable `delta_icc`.
- SIM `_voh_vol_table` must use the run model so overlay `vcc_list` shrinks band expand.
- Patch `psu_setup.time.sleep` (power_on_protected 1.5s) or SIM hangs.
- VOL live stays NOT_RUN. Do not invent G07 VOH.

## cite

ate/core/check_logic_dc_sim.py
ate/core/check_logic_dc.py
ate/config/parts/rs1g123.yaml
ate/config/parts/rs1g74.yaml
docs/LOGIC_DC_OPERATOR.md
