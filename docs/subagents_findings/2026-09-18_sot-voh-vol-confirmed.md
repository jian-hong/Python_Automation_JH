# Path B SoT VOH/VOL CONFIRMED (same lag as vcc_grid)

Date: 2026-09-18
Keywords: path-b, logic-dc, VOH, VOL, dc_limits, SoT, CONFIRMED, expand, push_pull, three_state, rs1g07, rs1g08, rs1g14, rs1g125, rs1gt34

## main_idea

Copy attached SoT `dc_limits.VOH/VOL` status+loads into part YAML. Path B `_voh_vol_table` prefers CONFIRMED `dc_limits` expansion (band onto merged `vcc_list`; named high-load at card VCC; formula VCC-0.1 only). UNCONFIRMED loads do not expand. Enable `voh` only for `push_pull` / `three_state` + CONFIRMED tables. G07 VOH stays N_A/SKIP; VOL SoT 6-load copy including 0.1mA and 24mA. Campaign Ariff `voh_table`/`vol_table` stay on 08/32/GT08/GT32. G07 campaign `vol_table` stays 4 extract rows. Do not copy ICCT/IOZ this turn even if SoT CONFIRMED.

## traps

- Same lag as vcc_grid: Code YAML `UNCONFIRMED` vs SoT CONFIRMED -- copy status+loads, do not invent extras.
- G07 VOH N_A -- never invent loads or enable voh. OD+voh FAIL.
- G07 campaign vol_table 4 extract rows stay Path A. SoT 0.1mA/24mA live in `dc_limits.VOL` only. Do not invert the campaign invent bars onto dc_limits.
- Enable voh only push_pull/three_state + CONFIRMED. G14/G125 must enable once tables exist. RS164 sequential: do not enable; UNCONFIRMED must not expand.
- `_expand_voh_vol_loads` requires `is_datasheet_signed`. Formula not VCC-0.1 is skipped (invent FAIL in check).
- Do not insert VOH/VOL under `pass_mode` (GT34 `voh: min_only` shares indent). Use unique dc_limits marker.
- Do not copy ICCT/IOZ even if SoT CONFIRMED (G125 IOZ @3.6V stay UNSURE this turn).
- Overlay/UI must not demote CONFIRMED vcc_grid. VOH/VOL overlay is not Customise Parameters this turn.
- SHA chicken-egg: content SHA in operator doc; git HEAD is stamp.

## cite

ate/tests/logic/logic_dc.py
ate/tests/logic/product_model.py
ate/core/check_logic_dc.py
ate/config/parts/rs1g08.yaml
ate/config/parts/rs1g07.yaml
ate/config/parts/rs1g14.yaml
ate/config/parts/rs1g32.yaml
ate/config/parts/rs1gt08.yaml
ate/config/parts/rs1gt32.yaml
ate/config/parts/rs1g125.yaml
ate/config/parts/rs1gt34.yaml
docs/LOGIC_DC_OPERATOR.md
