# LIVE matrix -- 24 CONFIRMED Path B (JH STARTS locally)

No remote LIVE. Operator owns instruments. Code owns config. DEMO/SIM is not Verify PASS.

Shared START: `START.bat` -> UI `127.0.0.1:5174` worker `8766` -> person selected -> Open Session -> Human Continue on `wire_map` -> START (not DEMO). Null `stable_eps_A` = NON_TIGHT. Fill **golden_auto** Version `workbook/` only. pretty / ultimate_manual `never_auto_write`. STS `sessions/datalog.md|.pdf` + Version-root `report.pdf`. `sessions/csv/` + `datapoints.csv` + `path_b_write.json`. Campaign `#Test_Database/Logic/<Part>/<Package>/<Operator>/Version_N/`.

Pin D&D `#logic-dc-flow` is **layout only** -- drag does not write product_model / wire_map. Form customise is SoT (truth / vcc_plan / pass_mode / loads). PSU_MSO hides Freq/Amp. excel_plots.status must match SoT; scale-wave plots stay UNCONFIRMED (enabled series only -- do not overstate unsigned loads).

SoT cards (scale-wave reconstruct; unsigned loads HOLD): `docs/datasheet/RS1G00_card_CONFIRMED.md` `RS1G02_card_CONFIRMED.md` `RS1G04_card_CONFIRMED.md` `RS1G86_card_CONFIRMED.md` `RS2G08_card_CONFIRMED.md` `RS2G32_card_CONFIRMED.md`. GT-wave: `RS1GT00_card_CONFIRMED.md` `RS1GT02_card_CONFIRMED.md` `RS1GT04_card_CONFIRMED.md` `RS1GT14_card_CONFIRMED.md` `RS2G00_card_CONFIRMED.md` `RS2G125_card_CONFIRMED.md` `RS2GT08_card_CONFIRMED.md`. FAIL bars: `docs/SCALE_WAVE_VERIFY_CHECKLIST_2026-09-21.md` `docs/GT_WAVE_VERIFY_CHECKLIST_2026-09-21.md`.

PARKED (not LIVE): RS1G74, RS1G123. HOLD process-only (not SIM 24): RS1GT125, RS1GT126 -- OE present, IOZ ABSENT, VOH/VOL UNSURE.

Settle: PSU -> settle -> measure. Voltage `stable_eps_V`. Current NON_TIGHT unless overlay `stable_eps_A`. PSU CH1=VCC always. PSU CH2=Y-load only when VOH/VOL ticked (VOH sink 0V; VOL source=VCC -- recable). DMM-on-VCC for ICC/delta_icc; DMM-on-Y for VOH/VOL/threshold; DMM-on-input for II; DMM-on-Y series for IOZ.

| Part | Test | Tick | Skip / HOLD | Wire | Stimulus | pass_mode | Continue |
|------|------|------|-------------|------|----------|-----------|----------|
| RS1GT34 | VIH/VIL | yes | -- | 1=NC 2=A 3=GND 4=Y 5=VCC. PSU CH1=VCC CH3=A. DMM Y | PSU_MSO hide Freq | VIH min_only; VIL max_only | CHA |
| RS1GT34 | ICC 2^1 | yes | -- | DMM-on-VCC series CH1 | PSU_MSO | icc max_only | CHA |
| RS1GT34 | delta_icc | yes | ICCT 3.4 -- do not invent 0.6 | DMM-on-VCC | PSU_MSO | delta_icc max_only | CHA |
| RS1GT34 | II | yes | -- | DMM series A | PSU_MSO | ii max_only | CHA |
| RS1GT34 | VOH | yes | IOZ OFF | PSU CH2 Y-load sink 0V. DMM Y | PSU_MSO | voh min_only | CHA. LIVE_PASS keep |
| RS1GT34 | VOL | yes | live.vol NOT_RUN until recable | **Recable** CH2 source=VCC first. DMM Y | PSU_MSO | vol max_only | CHA. Do not invent VOL |
| RS1G08 | VIH/VIL | yes | do not copy CMOS onto G00/G02 | 1=A 2=B 3=GND 4=Y 5=VCC. AWG CH1=A CH2=B | AWG pin_drive | VIH min_only; VIL max_only | CHA |
| RS1G08 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1G08 | delta_icc | yes | -- | DMM-on-VCC | AWG | delta_icc max_only | CHA |
| RS1G08 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA |
| RS1G08 | VOH | yes | IOZ OFF. excel_lock OFF | PSU CH2 Y-load sink 0V | AWG + CH2 load | voh min_only | CHA |
| RS1G08 | VOL | yes | -- | PSU CH2 Y-load source=VCC | AWG + CH2 load | vol max_only | CHA |
| RS1G07 | VIH/VIL | yes | -- | 1=NC 2=A 3=GND 4=Y 5=VCC. PSU CH3=A | PSU_MSO hide Freq | VIH min_only; VIL max_only | CHA |
| RS1G07 | ICC 2^1 | yes | -- | DMM-on-VCC | PSU_MSO | icc max_only | CHA |
| RS1G07 | delta_icc | yes | -- | DMM-on-VCC | PSU_MSO | delta_icc max_only | CHA |
| RS1G07 | II | yes | -- | DMM series A | PSU_MSO | ii max_only | CHA |
| RS1G07 | VOH | NO | **VOH N_A** forever | -- | -- | -- | do not tick / do not invent |
| RS1G07 | VOL | yes | Y=Z is not IOZ | PSU CH2 Y-load source=VCC | PSU_MSO | vol max_only | CHA |
| RS1G14 | VT+/- | yes tick vth | do not collapse to VIH. retention MAX UNSURE | 1=NC 2=A 3=GND 4=Y 5=VCC. PSU CH3=A | PSU_MSO hide Freq | VT+/VT-/HYST range | CHA |
| RS1G14 | ICC 2^1 | yes | -- | DMM-on-VCC | PSU_MSO | icc max_only | CHA |
| RS1G14 | delta_icc | yes | -- | DMM-on-VCC | PSU_MSO | delta_icc max_only | CHA |
| RS1G14 | II | yes | -- | DMM series A | PSU_MSO | ii max_only | CHA |
| RS1G14 | VOH | yes | -- | PSU CH2 sink 0V | PSU_MSO | voh min_only | CHA |
| RS1G14 | VOL | yes | -- | PSU CH2 source=VCC | PSU_MSO | vol max_only | CHA |
| RS1G32 | VIH/VIL | yes | -- | 1=A 2=B 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=B | mixed | VIH min_only; VIL max_only | CHA |
| RS1G32 | ICC 2^2 | yes | -- | DMM-on-VCC | mixed | icc max_only | CHA |
| RS1G32 | delta_icc | yes | -- | DMM-on-VCC | mixed | delta_icc max_only | CHA |
| RS1G32 | II | yes | -- | DMM series A/B | mixed | ii max_only | CHA |
| RS1G32 | VOH | yes | IOZ OFF | PSU CH2 sink 0V | mixed | voh min_only | CHA |
| RS1G32 | VOL | yes | -- | PSU CH2 source=VCC | mixed | vol max_only | CHA |
| RS1GT08 | VIH/VIL | yes | TTL 2.0-5.5 | 1=A 2=B 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=B | mixed | VIH min_only; VIL max_only | CHA |
| RS1GT08 | ICC 2^2 | yes | -- | DMM-on-VCC | mixed | icc max_only | CHA |
| RS1GT08 | delta_icc | yes | ICCT 3.4 -- do not invent 0.6 | DMM-on-VCC | mixed | delta_icc max_only | CHA |
| RS1GT08 | II | yes | -- | DMM series A/B | mixed | ii max_only | CHA |
| RS1GT08 | VOH | yes | -- | PSU CH2 sink 0V | mixed | voh min_only | CHA |
| RS1GT08 | VOL | yes | -- | PSU CH2 source=VCC | mixed | vol max_only | CHA |
| RS1GT32 | VIH/VIL | yes | TTL 2.0-5.5 | 1=A 2=B 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=B | mixed | VIH min_only; VIL max_only | CHA |
| RS1GT32 | ICC 2^2 | yes | -- | DMM-on-VCC | mixed | icc max_only | CHA |
| RS1GT32 | delta_icc | yes | ICCT 3.4 -- do not invent 0.6 | DMM-on-VCC | mixed | delta_icc max_only | CHA |
| RS1GT32 | II | yes | -- | DMM series A/B | mixed | ii max_only | CHA |
| RS1GT32 | VOH | yes | -- | PSU CH2 sink 0V | mixed | voh min_only | CHA |
| RS1GT32 | VOL | yes | -- | PSU CH2 source=VCC | mixed | vol max_only | CHA |
| RS1G125 | VIH/VIL | yes | -- | 1=OE 2=A 3=GND 4=Y 5=VCC. PSU CH3=A; AWG CH1=OE | PSU_MSO hide Freq | VIH min_only; VIL max_only | CHA |
| RS1G125 | ICC 2^(A+OE) | yes | -- | DMM-on-VCC | PSU_MSO | icc max_only | CHA |
| RS1G125 | delta_icc | yes | -- | DMM-on-VCC | PSU_MSO | delta_icc max_only | CHA |
| RS1G125 | II | yes | -- | DMM series A | PSU_MSO | ii max_only | CHA |
| RS1G125 | VOH | yes | -- | PSU CH2 sink 0V | PSU_MSO | voh min_only | CHA |
| RS1G125 | VOL | yes | -- | PSU CH2 source=VCC | PSU_MSO | vol max_only | CHA |
| RS1G125 | IOZ | yes | OE inactive H only (never active L). @3.6V UNSURE | DMM series Y. Force OE=H | PSU_MSO | ioz max_only | CHA |
| RS1G97 | VT+/- | yes tick vth | 3-in Schmitt. IOZ OFF | 1=B 2=GND 3=A 4=Y 5=VCC 6=C. AWG CH1=A CH2=B; PSU CH3=C | AWG+PSU | VT+/VT-/HYST range | CHA |
| RS1G97 | ICC 2^3 | yes | 8 corners | DMM-on-VCC | AWG+PSU | icc max_only | CHA |
| RS1G97 | delta_icc | yes | recipe.delta_offset_v 0.6 on 97 | DMM-on-VCC | AWG+PSU | delta_icc max_only | CHA |
| RS1G97 | II | yes | -- | DMM series A/B/C | AWG+PSU | ii max_only | CHA |
| RS1G97 | VOH | yes | -- | PSU CH2 sink 0V | AWG+PSU | voh min_only | CHA |
| RS1G97 | VOL | yes | -- | PSU CH2 source=VCC | AWG+PSU | vol max_only | CHA |
| RS1G126 | VIH/VIL | yes | -- | 1=OE 2=A 3=GND 4=Y 5=VCC. AWG CH1=A CH2=OE | AWG | VIH min_only; VIL max_only | CHA |
| RS1G126 | ICC 2^(A+OE) | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1G126 | delta_icc | yes | -- | DMM-on-VCC | AWG | delta_icc max_only | CHA |
| RS1G126 | II | yes | -- | DMM series A | AWG | ii max_only | CHA |
| RS1G126 | VOH | yes | -- | PSU CH2 sink 0V | AWG | voh min_only | CHA |
| RS1G126 | VOL | yes | -- | PSU CH2 source=VCC | AWG | vol max_only | CHA |
| RS1G126 | IOZ | yes | OE inactive L only (never active H) | DMM series Y. Force OE=L | AWG | ioz max_only | CHA |
| RS164 | Path B DC | NO | not combinational 2^n. VOH/VOL UNCONFIRMED. Ioff+ICCT ABSENT | 14-pin yaml map | sequential_shift_register | n/a | CHA. FAIL if treated as gate 2^n |
| RS1G00 | VIH/VIL | yes | bands HOLD. do not copy G08 CMOS | names only. AWG CH1=A CH2=B | AWG. NAND other=H invert | VIH/VIL not greenable | CHA |
| RS1G00 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1G00 | delta_icc | NO | ICCT ABSENT. delta_icc_uA HOLD | -- | -- | -- | do not invent ICCT |
| RS1G00 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA |
| RS1G00 | VOH | NO | unsigned loads HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS1G00 | VOL | NO | unsigned loads HOLD | -- | -- | -- | do not tick |
| RS1G00 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS1G02 | VIH/VIL | yes | TTL kind; band numbers HOLD. not G08 CMOS | names only. AWG CH1=A CH2=B | AWG. NOR other=L invert | bands HOLD | CHA |
| RS1G02 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1G02 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS1G02 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA |
| RS1G02 | VOH | NO | unsigned HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS1G02 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1G02 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS1G04 | VIH/VIL | yes | bands HOLD | names only. AWG CH1=A. NC not OE | AWG. INV Y=NOT A | bands HOLD | CHA |
| RS1G04 | ICC 2^1 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1G04 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS1G04 | II | yes | -- | DMM series A | AWG | ii max_only | CHA |
| RS1G04 | VOH | NO | unsigned HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS1G04 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1G04 | IOZ | NO | NC not OE | -- | -- | -- | do not tick |
| RS1G86 | VIH | HOLD | do not invent VIH_min | names only. AWG CH1=A CH2=B | AWG. XOR track+invert | VIH HOLD | CHA |
| RS1G86 | VIL | yes | 0.20*VCC @1.65-1.95 CONFIRMED. not G08 0.15*VCC | same | AWG | VIL max_only | CHA |
| RS1G86 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1G86 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS1G86 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA |
| RS1G86 | VOH | NO | unsigned HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS1G86 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1G86 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS2G08 | VIH/VIL | yes | bands HOLD. pin numbers HOLD | names only. AWG CH1=A CH2=B per channel | AWG. dual AND other=H track | bands HOLD | **CHA then CHB**. Do not skip rewire. Recable CHB after CHA Human Continue |
| RS2G08 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA then CHB |
| RS2G08 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS2G08 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA then CHB |
| RS2G08 | VOH | NO | unsigned HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS2G08 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2G08 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS2G32 | VIH/VIL | yes | bands HOLD. pin numbers HOLD | names only. AWG CH1=A CH2=B per channel | AWG. dual OR other=L track | bands HOLD | **CHA then CHB**. Do not skip rewire. Recable CHB after CHA Human Continue |
| RS2G32 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA then CHB |
| RS2G32 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS2G32 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA then CHB |
| RS2G32 | VOH | NO | unsigned HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS2G32 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2G32 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS1GT00 | VIH/VIL | yes | TTL kind; bands HOLD. do not copy G08 CMOS | names only. AWG CH1=A CH2=B | AWG. NAND other=H invert | bands HOLD | CHA |
| RS1GT00 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1GT00 | delta_icc | yes | ICCT 3.4 -- do not invent 0.6. Full uA HOLD | DMM-on-VCC | AWG | delta_icc max_only | CHA |
| RS1GT00 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA |
| RS1GT00 | VOH | NO | unsigned loads HOLD. excel_plots UNCONFIRMED | -- | -- | -- | do not tick |
| RS1GT00 | VOL | NO | unsigned loads HOLD | -- | -- | -- | do not tick |
| RS1GT00 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS1GT02 | VIH/VIL | yes | TTL kind; band numbers HOLD. not G08 CMOS | names only. AWG CH1=A CH2=B | AWG. NOR other=L invert | bands HOLD | CHA |
| RS1GT02 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1GT02 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS1GT02 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA |
| RS1GT02 | VOH | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1GT02 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1GT02 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS1GT04 | VIH/VIL | yes | bands HOLD | names only. AWG CH1=A. NC not OE | AWG. INV Y=NOT A | bands HOLD | CHA |
| RS1GT04 | ICC 2^1 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1GT04 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS1GT04 | II | yes | -- | DMM series A | AWG | ii max_only | CHA |
| RS1GT04 | VOH | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1GT04 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1GT04 | IOZ | NO | NC not OE | -- | -- | -- | do not tick |
| RS1GT14 | VT+/- | yes tick vth | do not invent VIH/VIL. do not copy G14 VT numbers | names only. AWG CH1=A. NC not OE | AWG. Schmitt INV | VT+/VT-/HYST range; numbers HOLD | CHA |
| RS1GT14 | ICC 2^1 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA |
| RS1GT14 | delta_icc | NO | ICCT ABSENT. do not copy G14 0.6 | -- | -- | -- | do not invent ICCT |
| RS1GT14 | II | yes | -- | DMM series A | AWG | ii max_only | CHA |
| RS1GT14 | VOH | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1GT14 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS1GT14 | IOZ | NO | NC not OE | -- | -- | -- | do not tick |
| RS2G00 | VIH/VIL | yes | bands HOLD. pin numbers HOLD | names only. AWG CH1=A CH2=B per channel | AWG. dual NAND other=H invert | bands HOLD | **CHA then CHB**. Do not skip rewire |
| RS2G00 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA then CHB |
| RS2G00 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS2G00 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA then CHB |
| RS2G00 | VOH | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2G00 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2G00 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS2G125 | VIH/VIL | yes | bands HOLD. pin numbers HOLD | names only. AWG CH1=A CH2=OE per channel | AWG. dual buf track OE=L | bands HOLD | **CHA then CHB**. Do not skip rewire |
| RS2G125 | ICC 2^(A+OE) | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA then CHB |
| RS2G125 | delta_icc | NO | ICCT ABSENT | -- | -- | -- | do not invent ICCT |
| RS2G125 | II | yes | -- | DMM series A | AWG | ii max_only | CHA then CHB |
| RS2G125 | VOH | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2G125 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2G125 | IOZ | yes | OE inactive H only (never active L). @3.6V UNSURE. do not invent uA | DMM series Y. Force OE=H | AWG | ioz max_only | CHA then CHB |
| RS2GT08 | VIH/VIL | yes | TTL kind; bands HOLD. not G08 CMOS. pin numbers HOLD | names only. AWG CH1=A CH2=B per channel | AWG. dual TTL AND other=H track | bands HOLD | **CHA then CHB**. Do not skip rewire |
| RS2GT08 | ICC 2^2 | yes | -- | DMM-on-VCC | AWG | icc max_only | CHA then CHB |
| RS2GT08 | delta_icc | NO | ICCT ABSENT. do not invent 0.6 | -- | -- | -- | do not invent ICCT |
| RS2GT08 | II | yes | -- | DMM series A/B | AWG | ii max_only | CHA then CHB |
| RS2GT08 | VOH | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2GT08 | VOL | NO | unsigned HOLD | -- | -- | -- | do not tick |
| RS2GT08 | IOZ | NO | oe none | -- | -- | -- | do not tick |
| RS1GT125 | Path B DC | HOLD | process-only. OE present. IOZ ABSENT. VOH/VOL UNSURE. not SIM 24 | names only | -- | -- | do not invent IOZ |
| RS1GT126 | Path B DC | HOLD | process-only. OE present active-H. IOZ ABSENT. VOH/VOL UNSURE. not SIM 24 | names only | -- | -- | do not invent IOZ |

Ready (SIM): 24 CONFIRMED visa-free catalog (RS164 skip sequential). HOLD stubs process-only. Not ready (LIVE): JH board-by-board START; unsigned loads HOLD; GT34 VOL recable first.
