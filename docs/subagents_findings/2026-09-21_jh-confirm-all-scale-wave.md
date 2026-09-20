# JH LAST-DAY UNLOCK CONFIRM-all scale wave

Date: 2026-09-21
Keywords: path-b, logic-dc, CONFIRM-all, rs1g00, rs1g02, rs1g04, rs1g86, rs2g08, rs2g32, CONFIRMED, VIL 0.20*VCC, TTL, dual_channel_continue, 17 SIM, no invent, G07 VOH N_A

## main_idea

JH LAST-DAY UNLOCK 2026-09-21 Asia/Kuala_Lumpur treats on-disk DRAFT cards as CONFIRM. Promote G00/G02/G04/G86/2G08/2G32 function/truth/isolation CONFIRMED. G86 vcc_grid VIL 0.20*VCC @1.65-1.95 CONFIRMED; VIH HOLD. Empty vcc_grid / VOH / VOL / delta_icc stay UNCONFIRMED. ICCT ABSENT. Enable input_threshold/icc/ii only. SIM `_ACTIVE_LOGIC` = 17. PARKED G74/G123 stay out. Do not copy G08 CMOS onto G02. Do not invent loads/ICCT/pin numbers.

## locks

- G00 NAND other=H invert; G02 NOR other=L invert TTL not CMOS; G04 INV NC not OE; G86 XOR track+invert VIL 0.20*VCC; 2G CHA then CHB
- OE/IOZ OFF; ICCT ABSENT != invent ICCT; delta_icc_uA HOLD no numbers
- G07 VOH N_A forever
- applicable_path_b_dc skips voh/vol without CONFIRMED tables (fail-closed, not invent)

## cite

ate/config/parts/rs1g00.yaml
ate/core/check_logic_dc.py `_next_wave_ok`
ate/core/check_logic_dc_sim.py `_ACTIVE_LOGIC`
HANDOVER.md CONFIRM-all
