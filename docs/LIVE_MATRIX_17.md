# LIVE matrix -- 17 CONFIRMED Path B (JH STARTS locally)

No remote LIVE. Operator owns instruments. Code owns config. DEMO/SIM is not Verify PASS.

Shared START: `START.bat` -> UI `127.0.0.1:5174` worker `8766` -> person selected -> Open Session -> Human Continue on `wire_map` -> START (not DEMO). Null `stable_eps_A` = NON_TIGHT. Fill **golden_auto** Version `workbook/` only. pretty / ultimate_manual `never_auto_write`. STS `sessions/datalog.md|.pdf` + Version-root `report.pdf`. `sessions/csv/` + `datapoints.csv` + `path_b_write.json`. Campaign `#Test_Database/Logic/<Part>/<Package>/<Operator>/Version_N/`.

Pin D&D `#logic-dc-flow` is **layout only** -- drag does not write product_model / wire_map. Form customise is SoT (truth / vcc_plan / pass_mode / loads). PSU_MSO hides Freq/Amp. excel_plots.status must match SoT; scale-wave plots stay UNCONFIRMED (enabled series only -- do not overstate unsigned loads).

SoT cards (scale-wave reconstruct; unsigned loads HOLD): `docs/datasheet/RS1G00_card_CONFIRMED.md` `RS1G02_card_CONFIRMED.md` `RS1G04_card_CONFIRMED.md` `RS1G86_card_CONFIRMED.md` `RS2G08_card_CONFIRMED.md` `RS2G32_card_CONFIRMED.md`.

PARKED (not LIVE): RS1G74, RS1G123.

| Part | Tick (Path B DC) | Skip / HOLD | Wire (pin_drive + pins) | Stimulus / settle | pass_mode | Continue |
|------|------------------|-------------|-------------------------|-------------------|-----------|----------|
| RS1GT34 | VIH/VIL, ICC 2^1, delta_icc (ICCT 3.4), II, VOH, VOL | IOZ OFF (oe none) | 1=NC 2=A 3=GND 4=Y 5=VCC. PSU CH1=VCC CH2=Y-load CH3=A. DMM/SCOPE on Y | PSU_MSO (hide Freq). VOH LIVE_PASS keep. **VOL recable** CH2 sink 0V -> source=VCC first | VIH min_only; VIL/VOL/icc/ii/delta max_only; VOH min_only | CHA only. live.vol NOT_RUN until recable session |
| RS1G08 | VIH/VIL, ICC 2^2, delta_icc, II, VOH, VOL | IOZ OFF. Path B excel_lock OFF (sheet_map) | 1=A 2=B 3=GND 4=Y 5=VCC. AWG CH1=A CH2=B | pin_drive AWG. CMOS bands CONFIRMED. Do not copy onto G00/G02 | VIH min_only; VIL/VOL/icc/ii/delta max_only; VOH min_only | CHA only |
| RS1G07 | VIH/VIL, ICC 2^1, delta_icc, II, VOL | **VOH N_A** forever. IOZ OFF (Y=Z is not IOZ) | 1=NC 2=A 3=GND 4=Y 5=VCC. PSU CH3=A | PSU_MSO hide Freq. Do not tick voh | VIL/VOL/icc/ii/delta max_only | CHA only |
| RS1G14 | VT+/- (tick vth), ICC 2^1, delta_icc, II, VOH, VOL | Do not collapse VT+/- to VIH. retention MAX UNSURE | 1=NC 2=A 3=GND 4=Y 5=VCC. PSU CH3=A | PSU_MSO hide Freq. Schmitt range | VT+/VT-/HYST range; VOH min_only; VOL/icc/ii/delta max_only | CHA only |
| RS1G32 | VIH/VIL, ICC 2^2, delta_icc, II, VOH, VOL | IOZ OFF | 1=A 2=B 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=B | OR other=L track | VIH min_only; VIL/VOL/icc/ii/delta max_only; VOH min_only | CHA only |
| RS1GT08 | VIH/VIL, ICC 2^2, delta_icc, II, VOH, VOL | TTL ICCT 3.4 -- do not invent 0.6 | 1=A 2=B 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=B | TTL 2.0-5.5 | VIH min_only; VIL/VOL/icc/ii/delta max_only; VOH min_only | CHA only |
| RS1GT32 | VIH/VIL, ICC 2^2, delta_icc, II, VOH, VOL | TTL ICCT 3.4 -- do not invent 0.6 | 1=A 2=B 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=B | TTL 2.0-5.5 | VIH min_only; VIL/VOL/icc/ii/delta max_only; VOH min_only | CHA only |
| RS1G125 | VIH/VIL, ICC 2^(A+OE), II, delta_icc, VOH, VOL, IOZ | IOZ only OE inactive H (never active L). IOZ @3.6V UNSURE | 1=OE 2=A 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=OE | PSU_MSO hide Freq | VIH min_only; VIL/VOL/icc/ii/delta/ioz max_only; VOH min_only | CHA only |
| RS1G97 | VT+/- (vth), ICC 2^3, delta_icc, II, VOH, VOL | IOZ OFF (oe none). 3-in Schmitt | 1=B 2=GND 3=A 4=Y 5=VCC 6=C. AWG CH1=A CH2=B; PSU CH3=C | Schmitt range. ICC 8 corners | VT+/VT-/HYST range; VOH min_only; VOL/icc/ii/delta max_only | CHA only |
| RS1G126 | VIH/VIL, ICC 2^(A+OE), delta_icc, II, VOH, VOL, IOZ | IOZ only OE inactive L (never active H) | 1=OE 2=A 3=GND 4=Y 5=VCC. AWG CH1=A CH2=OE | AWG. No C pin | VIH min_only; VIL/VOL/icc/ii/delta/ioz max_only; VOH min_only | CHA only |
| RS164 | none Path B DC (SIM skip) | not combinational 2^n. VOH/VOL UNCONFIRMED. Ioff+ICCT ABSENT | 14-pin map on yaml. Do not tick icc/vth/voh/vol/ioz/delta | sequential_shift_register | n/a Path B gate | CHA only. FAIL if treated as gate 2^n |
| RS1G00 | VIH/VIL (unsigned HOLD), ICC 2^2, II | VOH/VOL/delta/IOZ OFF. excel_plots UNCONFIRMED | pins names only (numbers HOLD). AWG CH1=A CH2=B | AWG. NAND other=H invert. Do not copy G08 CMOS | icc/ii max_only. VIH/VIL not greenable until bands signed | CHA only |
| RS1G02 | VIH/VIL (TTL kind; bands HOLD), ICC 2^2, II | VOH/VOL/delta/IOZ OFF. excel_plots UNCONFIRMED | pins names only. AWG CH1=A CH2=B | AWG. NOR other=L invert. Not G08 CMOS 0.65/0.15 | icc/ii max_only. bands HOLD | CHA only |
| RS1G04 | VIH/VIL (unsigned HOLD), ICC 2^1, II | VOH/VOL/delta/IOZ OFF. NC not OE. excel_plots UNCONFIRMED | pins names only. AWG CH1=A | AWG. INV Y=NOT A | icc/ii max_only | CHA only |
| RS1G86 | VIL 0.20*VCC @1.65-1.95 CONFIRMED; VIH HOLD; ICC 2^2; II | VOH/VOL/delta/IOZ OFF. excel_plots UNCONFIRMED | pins names only. AWG CH1=A CH2=B | AWG. XOR track other=L + invert other=H. Not G08 VIL 0.15*VCC | VIL max_only on signed fragment. VIH HOLD | CHA only |
| RS2G08 | VIH/VIL (unsigned HOLD), ICC 2^2, II | VOH/VOL/delta/IOZ OFF. pin numbers HOLD. excel_plots UNCONFIRMED | names only -- do not invent 8-pin map. AWG CH1=A CH2=B per channel | AWG. dual AND other=H track | icc/ii max_only | **CHA then CHB**. Do not skip rewire. Recable CHB after CHA Human Continue |
| RS2G32 | VIH/VIL (unsigned HOLD), ICC 2^2, II | VOH/VOL/delta/IOZ OFF. pin numbers HOLD. excel_plots UNCONFIRMED | names only -- do not invent 8-pin map. AWG CH1=A CH2=B per channel | AWG. dual OR other=L track | icc/ii max_only | **CHA then CHB**. Do not skip rewire. Recable CHB after CHA Human Continue |

Ready (SIM): 17 CONFIRMED visa-free catalog (RS164 skip sequential). Not ready (LIVE): JH board-by-board START; scale-wave unsigned loads HOLD; GT34 VOL recable first.
