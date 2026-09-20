# Path B Logic DC -- AE/FAE handover

JH last day unlock **2026-09-21 Asia/Kuala_Lumpur**. **CONFIRM-all** scale wave: G00/G02/G04/G86/2G08/2G32 on-disk DRAFT cards are Datasheet-signed **CONFIRMED** for function/truth/isolation (G86 VIL fragment too). Unsigned cells stay fail-closed. PARKED is not scale. DEMO/SIM is not a reproduce / not Verify PASS.

Canonical twin: `docs/LOGIC_DC_HANDOVER.md` (same map). Operator bench: `docs/LOGIC_DC_OPERATOR.md`. Writer format: `docs/LOGIC_DC.md`. Dual Continue: `docs/LOGIC_DC_DUAL_CHANNEL.md`.

## Tomorrow without JH

1. GT34 **VOL board-change resume** (LIVE). Do not invent VOL. Keep VOH LIVE table as-is.
2. LIVE the **CONFIRM-all** scale-wave families (NAND/NOR/INV/XOR/dual AND/dual OR) per the family recipes below. Unsigned VOH/VOL/VIH (except G86 VIL) stay **numbers HOLD**. Do not copy G08 CMOS onto G02. Do not invent ICCT.
3. RS74AUP1G07 wait sample -- do not copy RS1G07 numbers. RS29511 / RS1GT32D stay Path A.
4. Do not unpark G74/G123. Do not treat sequential as gate 2^n.
5. New SKU = YAML only. Do not fork `logic_dc.py`. Run `python -m ate.core.check_logic_dc` before claiming green.

## How to add a new Logic DC part (no new Python)

Stop at the first row that fails. Missing card = HOLD, not invent.

1. **PDF** -- local Reference extract under `ate/config/datasheets/text/` (or attached card). Do not scrape en.run-ic.com.
2. **OCR card** -- PaddleOCR onto `docs/datasheet/card_fields.schema.yaml` objects: Part, Pin, TruthTable, Isolation, Limit, Recipe. Setup Logic DC panel: assign / edit / delete per field. Do not install Baidu unless asked.
3. **CONFIRM** -- Datasheet-signed `product_model.status: CONFIRMED` (and truth_table / isolation / `vcc_grid` as signed). Until then `UNCONFIRMED` -- numbers HOLD, not greenable. Panel Save product_model cannot promote signed.
4. **Copy** `product_model` into `ate/config/parts/<key>.yaml`. Isolation derives from truth_table (track if a combo holds the other pins; invert only if no track). Do not invent pin numbers, loads, or ICCT maps.
5. **Enable tests** that the card allows:
   - combinational: `input_threshold` (or `vth` if Schmitt), `icc`, `ii`, `voh`/`vol` only if CONFIRMED loads + push_pull/three_state
   - OE present: `ioz` only when OE inactive (`recipe.ioz_when`)
   - open-drain: do **not** tick `voh` (VOH N_A)
   - sequential: Path B gate ids OFF (not 2^n)
   - delta_icc only from card ICCT / `delta_icc_uA` -- ICCT ABSENT is not a map
6. **SIM** -- `python -m ate.core.check_logic_dc` then `python -m ate.core.check_logic_dc_sim`. Overlay one VCC. `stable_eps_A` null = NON_TIGHT. Not a bench green.
7. **LIVE** -- START.bat, person selected, Open Session, Human Continue on wire_map. PSU -> settle -> measure. Fill **golden_auto** Version xlsx only. pretty / ultimate_manual never auto. STS `sessions/datalog.pdf` + Version-root `report.pdf`. `sessions/csv/` + `datapoints.csv` + `path_b_write.json`.

Campaign tree: `#Test_Database/Logic/<Part>/<Package>/<Operator>/Version_N/`. Idle-restart worker after Python. Ctrl+F5 after UI/yaml.

## Path B parts (status)

### CONFIRMED (17) -- SIM mandatory; status gate only until LIVE

| Part | Function lock | SIM | Live / blocked |
|------|---------------|-----|----------------|
| RS1GT34 | buffer n=1 Y=A; PSU_MSO; ICCT 3.4 | SIM green | VOH LIVE_PASS; VOL NOT_RUN (board change) |
| RS1G08 | AND-2 other=H; no IOZ; AWG | SIM green | none |
| RS1G07 | open-drain; VOH N_A | SIM green | do not invent VOH |
| RS1G14 | Schmitt VT+/- ; tick vth | SIM green | retention MAX UNSURE |
| RS1G32 | OR-2 other=L | SIM green | none |
| RS1GT08 | TTL AND; ICCT 3.4 not 0.6 | SIM green | none |
| RS1GT32 | TTL OR; ICCT 3.4 not 0.6 | SIM green | none |
| RS1G125 | OE active-L; IOZ when OE inactive H | SIM green | IOZ @3.6V UNSURE |
| RS1G97 | 3-in Schmitt; ICC 2^3; no IOZ | SIM green | status gate only |
| RS1G126 | OE active-H; IOZ when OE inactive L | SIM green | status gate only |
| RS164 | sequential_shift_register | SIM skip | not combinational 2^n; VOH/VOL UNCONFIRMED; Ioff+ICCT ABSENT |
| RS1G00 | NAND other=H invert; oe none; IOZ OFF; ICCT ABSENT | SIM green | unsigned VIH/VIL/VOH/VOL HOLD |
| RS1G02 | NOR other=L invert; TTL VIH/VIL (not G08 CMOS) | SIM green | unsigned bands HOLD |
| RS1G04 | INV n=1 Y=NOT A; NC not OE; IOZ OFF | SIM green | unsigned VIH/VIL/VOH/VOL HOLD |
| RS1G86 | XOR track+invert; VIL 0.20*VCC @1.65-1.95 | SIM green | VIH/VOH/VOL HOLD |
| RS2G08 | dual AND; CHA then CHB Continue | SIM green | pin numbers HOLD; unsigned loads HOLD |
| RS2G32 | dual OR; CHA then CHB Continue | SIM green | pin numbers HOLD; unsigned loads HOLD |

`check_logic_dc` FAIL: invent OE/IOZ, invent ICCT, wrong G02/G86 bands, skip CHA->CHB, invent delta_icc numbers, invent VOH/VOL loads.

### PARKED (2) -- optional archive; not mandatory SIM

| Part | Runner | Locks |
|------|--------|-------|
| RS1G74 | sequential_dff_clr_pre | yaml `status: PARKED`; product_model UNCONFIRMED; Path B OFF; FAIL if gate 2^n |
| RS1G123 | sequential_monostable_rc | same; ICCT ABSENT; schmitt false; missing yaml does not block green |

### Inventory Logic without Path B product_model (gaps only -- no invent)

| Part | Why | Do |
|------|-----|----|
| RS74AUP1G07 | wait sample; no Datasheet card | gaps[] only; do not copy G07 |
| RS29511 | Path A Soo suite | keep Path A; no Path B product_model |
| RS1GT32D | Path A Ariff; not RS1GT32XC5 | keep Path A; do not copy GT32 CONFIRMED |

RS0204 is Level/dual-rail (`rs0204.py`) -- never a Path B product_model.

## LIVE each family (CONFIRM-all scale wave)

Shared LIVE start: START.bat, person selected, Open Session, Human Continue after wire_map, START not DEMO, null `stable_eps_A` = NON_TIGHT, fill golden_auto only, pretty never auto. Tick `input_threshold` + `icc` + `ii`. Do **not** tick `voh`/`vol`/`delta_icc`/`ioz` on these six until a card has loads / ICCT / OE.

1. **LIVE NAND (RS1G00)** -- AWG A/B. Isolation other=H invert. Campaign `#Test_Database/Logic/RS1G00/...`. Do not copy G08 CMOS 0.65/0.15. ICCT ABSENT.
2. **LIVE NOR (RS1G02)** -- AWG A/B. Isolation other=L invert. TTL-style VIH/VIL kind lock; band numbers HOLD. Do not copy G08 CMOS.
3. **LIVE INV (RS1G04)** -- AWG A only. n=1 Y=NOT A. NC is not OE. Do not tick IOZ.
4. **LIVE XOR (RS1G86)** -- AWG A/B. Dual isolation track (other=L) + invert (other=H). Judge **VIL <= 0.20*VCC** at 1.65-1.95 (`max_only`). VIH HOLD -- do not invent. Do not copy G08 VIL 0.15*VCC.
5. **LIVE dual AND (RS2G08)** -- CHA then CHB Continue. Recable Channel B after CHA Human Continue. Isolation other=H track. Pin numbers HOLD. Extra `rs2g*.yaml` forbidden.
6. **LIVE dual OR (RS2G32)** -- same CHA then CHB Continue. Isolation other=L track. Pin numbers HOLD.

G07 VOH stays N_A forever. Do not unpark G74/G123.

## Physics locks (do not weaken)

| Lock | Rule |
|------|------|
| G07 / open-drain | no VOH; hide/skip VOH on panel; Y=Z is not IOZ |
| G14 / Schmitt | VT+ / VT- / dVT (range). Do not collapse to single VIH |
| OE -> IOZ | IOZ only when OE inactive. G126 active-H -> IOZ OE=L. G125 active-L -> IOZ OE=H. oe none -> IOZ OFF |
| sequential != 2^n | RS164 / G74 / G123: Path B icc / delta_icc / vth / voh / vol / ioz OFF. `sim_icc_plan` n=0 |
| 2G CHA then CHB | `recipe.dual_channel_continue` + `channels: [CHA, CHB]`. 1Gxx off. Extra `rs2g*.yaml` without Datasheet card forbidden |
| delta_icc | from card ICCT symbol (`one_input_V` / `offset_v`) or `delta_icc_uA` only. ICCT ABSENT != invent. Do not invent 0.6 |
| VOH/VOL | CONFIRMED `dc_limits` loads only (formula VCC-0.1). Do not invent extra loads |
| `stable_eps_A` | null = NON_TIGHT. Do not reuse `stable_eps_V` as amps |
| overlay | must not stamp UNCONFIRMED over CONFIRMED `vcc_grid` |
| G02 TTL | not G08 CMOS 0.65*VCC / 0.15*VCC |
| G86 VIL | 0.20*VCC @1.65-1.95 from card; VIH HOLD |

## Customise Parameters (Setup Logic DC recipe)

Works from product_model -- no xyflow, no per-SKU Python.

- **n-input:** `logic_inputs` length; ICC corners = 2^n (OE extra when present). Sequential shows 0.
- **OE:** meta + IOZ row only if OE on card (inactive only).
- **Schmitt:** FIXED POINTS / RANGE SWEEPS show VT+ / VT- / HYST, not plain VIH/VIL.
- **Open-drain:** VOH N/A skip on limits table; do not tick voh.
- **Dual-channel Continue:** checkbox CHA then CHB (2Gxx). Off on 1Gxx.
- **Stimulus:** PSU_MSO hides Freq/Amp. AWG keeps them.
- Save Version overlay -> `_manifest/test_params.yaml`. Save product_model -> part yaml via card_fields. Cannot CONFIRM from the panel.

## STS / Excel / CSV

| Output | Policy |
|--------|--------|
| Version `workbook/` golden_auto | overwrite-in-place (`one_per_version_overwrite`) |
| pretty / ultimate_manual | `never_auto_write` |
| `sessions/csv/` + `datapoints.csv` | Path B auto with golden_auto |
| `sessions/path_b_write.json` | fill log |
| `sessions/datalog.md\|.html\|.pdf` | STS |
| Version-root `report.pdf` | copies measured + Pass criteria / How met -- never invent pass numbers |
| `{test}/DUT_n/records/` | per-DUT records; FAIL photo here |

Never an orphan second Version xlsx. Never invent sheet_map cells -- `campaign_outline` / existing `paste.values` only.

## GT34 VOL board-change resume (LIVE)

Board is still **VOH-wired** after JH room 2026-09-18 VOH LIVE_PASS. Do not invent VOL. `product_model.live.vol.status` is NOT_RUN until this session.

1. START.bat. Person selected. Campaign `#Test_Database/Logic/RS1GT34/...`. Open Session.
2. Recable PSU CH2 Y-load: VOH was sink rail 0V; VOL is source rail = VCC. Keep CH1=VCC, CH3=A, DMM/SCOPE on Y. PSU_MSO -- no AWG Freq/Amp.
3. Human Continue after wire_map verify. Tick `vol` (CONFIRMED loads already on the card). Judge **VOL <= max** (`max_only`).
4. START (not DEMO). PSU -> settle -> measure. Null `stable_eps_A` = NON_TIGHT.
5. Fill golden_auto Version xlsx. Export STS. Do not write pretty. Do not copy VOH LIVE numbers onto VOL or onto other SKUs.
6. After LIVE, set `live.vol` from that session only. Leave other ids unchanged.

VOH LIVE (keep; min_only PASS): -8mA@2.0 1.7089; -24mA@3.3 2.8968; -32mA@4.5 4.0695; -32mA@5.0 4.5867; -32mA@5.5 5.0992.

## Local-ready Path B tree

Do not fork these. Missing file = not local-ready.

- `ate/tests/logic/logic_dc.py` (shared runner) + alias `ate/tests/logic/dc.py`
- `ate/tests/logic/product_model.py`
- `ate/tests/logic/threshold_search.py`
- `ate/tests/logic/excel_lock.py`
- `ate/core/check_logic_dc.py` + `ate/core/check_logic_dc_sim.py`
- `docs/datasheet/card_fields.schema.yaml`
- `ate/config/parts/` CONFIRMED + UNCONFIRMED + PARKED yamls above

Checks: `python -m ate.core.check_logic_dc` and `python -m ate.core.check_logic_dc_sim`.

No Verify PASS claimed from this page.
