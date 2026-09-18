# Park G74/G123 + UNCONFIRMED next-wave bind

Date: 2026-09-18
Keywords: path-b, logic-dc, PARKED, rs1g74, rs1g123, rs1g00, rs1g02, rs1g04, rs1g86, rs2g08, rs2g32, UNCONFIRMED, numbers HOLD, dual_channel_continue, NAND, NOR, XOR, ICCT ABSENT

## main_idea

JH dropped G74/G123 -- part yaml `status: PARKED`, `product_model.status` stays UNCONFIRMED, Path B ids OFF, FAIL if treated as combinational 2^n. Optional archive: missing yaml does not block green. Next-wave G00/G02/G04/G86/2G08/2G32 bound UNCONFIRMED (no ate_ds_extract/models in workspace). Numbers HOLD. No CONFIRM. 11 CONFIRMED SIM unchanged (next-wave not in `_ACTIVE_LOGIC`).

## locks

- G00 NAND other=H invert; ICCT ABSENT on all six; delta_icc from delta_icc_uA only (no invent ICCT map / numbers)
- G02 NOR other=L invert; TTL-style VIH/VIL -- FAIL G08 CMOS 0.65/0.15 copy
- G04 inverter n=1; NC not OE; IOZ OFF
- G86 XOR track+invert; VIL 0.20*VCC @1.65-1.95 from card
- 2G08/2G32 dual_channel_continue CHA then CHB; FAIL skip CHA->CHB; no invent OE/IOZ

## cite

ate/config/parts/rs1g74.yaml
ate/config/parts/rs1g123.yaml
ate/config/parts/rs1g00.yaml
ate/core/check_logic_dc.py `_next_wave_ok`
docs/LOGIC_DC_DUAL_CHANNEL.md
