# SOOT: scale-wave stay UNCONFIRMED DRAFT

Date: 2026-09-20
Keywords: path-b, SOOT, JH DM unlock, Datasheet CONFIRM, VOID, rs1g00, rs1g02, rs1g04, rs1g86, rs2g08, rs2g32, UNCONFIRMED, numbers HOLD, 11 SIM, no invent

## main_idea

ATE Datasheet / Product Model / Verify: scale-wave cards are still DRAFT. JH DM unlock != Datasheet CONFIRM. CONFIRM-all 2026-09-21 is VOID. Revert G00/G02/G04/G86/2G08/2G32 product_model.status + nested truth_table / isolation / vcc_grid / excel_plots to UNCONFIRMED. Keep function bind, enabled_tests honesty (input_threshold/icc/ii on; voh/vol/ioz/delta_icc off), physics locks, D&D UI from 086b8ec. Do not invent signed loads. check_logic_dc numbers gate FAIL/HOLD on unsigned -- check PASSES while UNCONFIRMED (`_next_wave_ok` must not call `_fail_closed_until_signed`). 11 prior CONFIRMED SIM unchanged. PARKED G74/G123 unchanged. G86 VIL 0.20*VCC formula stays as function bind; vcc_grid.status UNCONFIRMED.

## locks

- `_CONFIRMED_SIM_PARTS` / `_ACTIVE_LOGIC` = 11; `set(_NEXT_WAVE) & set(_CONFIRMED_SIM)` FAIL
- `_next_wave_ok` requires UNCONFIRMED (FAIL if Datasheet-signed); G86 vcc_grid UNCONFIRMED
- no invent OE/IOZ/ICCT/VOH/VOL loads; G02 TTL not G08 CMOS; 2G CHA then CHB
- G07 VOH N_A forever

## cite

ate/config/parts/rs1g00.yaml
ate/core/check_logic_dc.py `_next_wave_ok`
ate/core/check_logic_dc_sim.py `_ACTIVE_LOGIC`
HANDOVER.md CONFIRM-all VOID
docs/subagents_findings/2026-09-21_jh-confirm-all-scale-wave.md VOID
docs/subagents_findings/2026-09-18_scale-wave-park.md
