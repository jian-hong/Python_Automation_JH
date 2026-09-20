# Path B Logic DC -- operator

**PR #5 HEAD SHA:** `ecd7578`

This file is the bench/operator map. Writer/import format stays in `docs/LOGIC_DC.md`. Verify is a separate agent. This page is **not** a reproduce claim and does **not** claim Verify PASS / bench green.

Settle loop (this PR): recipe `settle_s=0.05`, `stable_n=3`, `stable_eps_V=0.005`, `settle_timeout_s=2.0`. Voltage (VOH/VOL/threshold) waits eps/N vs `stable_eps_V`. Current (ICC / ΔICC / II / IOZ) uses `stable_eps_A` only -- 97/126 default is **null**. Do **not** reuse `stable_eps_V` as amps (0.005 V would be a 5 mA window). Do **not** invent a uA epsilon.

- Tight settle-to-stable (`stable_eps_A` set via panel / `_manifest/test_params.yaml` overlay): eps/N + hard timeout. Timeout raises `RuntimeError` / FAIL. It does **not** return the last reading.
- Null `stable_eps_A`: tight-settle **claims** stay FAIL-closed. Honest path waits `settle_s` once then measures and tags `settle=NON_TIGHT` (not greenable as tight-settle).
- Ground `stable_eps_A` (amps) on the Logic DC panel overlay before claiming current settle-to-stable.

`check_logic_dc` also FAIL-closes **enabled-but-unrunnable** ids: every part `enabled_tests` id must have a registered `TestSpec` with callable `run` (no stub). Enabled `voh`/`vol` without CONFIRMED `dc_limits.VOH/VOL.loads` expansion or campaign `voh_table`/`vol_table` rows FAIL the same gate. Enable `voh` only for `push_pull` / `three_state` + CONFIRMED tables (open-drain G07 VOH stays N_A/SKIP). Enabled 97/126 tests with empty `wire_map` or missing `data_paths` FAIL too. Never invent nets.

## Copy-ready Version folder

Paste this tree under the campaign. Launch with **START.bat** in this folder (zip operators) or the zip root -- same console everywhere.

```
#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/
  START.bat                 # copy-ready: same START.bat as zip root
  report.pdf                # latest STS report (overwrite after Version run)
  workbook/                 # golden_auto lab xlsx (never ultimate_manual)
  workbook/*_datapoints.csv # full session rows beside golden_auto (pretty never auto)
  _manifest/sheet_map.yaml  # folder <-> sheet <-> paste anchors
  _manifest/test_params.yaml
  sessions/report.json
  sessions/datalog.md        # STS datalog (also .html / .pdf)
  sessions/csv/              # Path B auto CSV (pretty never auto)
  sessions/path_b_write.json # Path B fill log (overwrite-in-place)
  {test}/DUT_n/records/
  {test}/DUT_n/              # FAIL scope PNG / photo attach
```

Excel folder template (folders only -- never invent cells):

`#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/workbook/`

`data_paths` on the 97/126/34 product_model (panel show/edit/delete): `excel` / `sessions/report.json` / `sessions/datalog.md` / `sessions/csv/` / `report.pdf` / `{test}/DUT_n/records/` / attach `{test}/DUT_n/`.

## AE/FAE Continue (no-code)

Every enabled Path B TestSpec run (DC in `logic_dc.py`, AC `tp`/`ten`/`tdis` in `wraps.py`) surfaces Continue prompts. `wire_map` comes from CONFIRMED `pins` + `pin_drive` only. Human Continue after verify. Never invent nets.

1. **Wire map** -- PSU CH->pin, AWG CH->input, DMM->VCC or Y, SCOPE CH->Y/debug. From `product_model.wire_map`.
2. **Stimulus** -- Vcc / force `pin_drive` / truth_table vector.
3. **Settle** -- `settle_prompt` show wait. Voltage eps/N (`stable_eps_V`). Current: NON_TIGHT if `stable_eps_A` null, else tight eps/N + timeout hard-FAIL.
4. **Measure + pass_mode**.
5. **On FAIL** -- prompt scope capture / photo -> session attach path `{test}/DUT_n/`.
6. **Save path shown** after run: Excel `#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/workbook/` + `sessions/report.json` + `sessions/csv/` + STS datalog + Version `report.pdf` + `{test}/DUT_n/records/`.

Panel: show / edit / delete `wire_map`, `settle_prompt`, `data_paths` (card_fields.schema.yaml). Cannot promote Datasheet-signed.

## TestSpec <-> OOP

Field list: `docs/datasheet/card_fields.schema.yaml` (OOP_SCHEMA). Setup Logic DC panel bind: each card field is individually assignable / editable / deletable. Save product_model writes those keys. Cannot promote Datasheet-signed. Do not invent loads.

| TestSpec | OOP | Body |
|----------|-----|------|
| `tp` / `ten` / `tdis` | Recipe (AC) | `wraps.py` (real wrap) |
| `input_threshold` / `vth` | Pin + TruthTable + Isolation + Recipe | `logic_dc.py` |
| `icc` / `delta_icc` / `ii` | Pin + Recipe + Limit | `logic_dc.py` |
| `voh` / `vol` | Pin + TruthTable + Limit + Recipe | `logic_dc.py` |
| `ioz` | Pin + Recipe + Limit | `logic_dc.py` (OE only) |

Part / Pin / TruthTable / Isolation / Limit / Recipe are the OOP objects on the card. OCR (PaddleOCR, already chosen -- do **not** install Baidu unless asked) maps each token onto one of those fields; the operator can assign, edit, or delete that field on the panel.

See Lim (`seelim_dc.py` locator) and Ariff (`ariff_dc.py` RS1G08 `voh_load`) are **read-only refs**. Do not copy See Lim / Ariff params into 97/126 Path B cards.

## DEMO / SIM -- enough (not a reproduce)

Use these without a live DMM/PSU/AWG. They prove schema and UI, **not** instrument physics. Zip DEMO still starts from **START.bat**.

1. Product-model schema load (`ate/config/parts/<key>.yaml` `product_model` / `logic_dc:`). Isolation derives from `truth_table` (Y tracks the swept pin; invert only if no track combo).
2. `pass_mode` on part yaml + limits yaml + Setup **Logic DC recipe** / Test program (range / min_only / max_only / fail-open / unspec). Missing min/max stay **unspec** unless fail-open.
3. Fail-closed until Datasheet-signed **CONFIRMED**. UNCONFIRMED SKUs cannot green. RS1G97 and RS1G126 are CONFIRMED (Jian Hong 2026-09-17) for the status gate only -- that is not a bench green. RS1GT34 is Path B **CONFIRMED** (Jian Hong 2026-09-18) for the status gate only -- that is not a bench green.
4. Panel recipe edit: JSON **Save product_model** writes part yaml from `docs/datasheet/card_fields.schema.yaml` (cannot promote to Datasheet-signed). **Customise Parameters** (pin/wiring map labels, 2Gxx dual-channel Continue switch, FIXED POINTS chips + RANGE SWEEPS, merged `vcc_list` preview, per-band limits + `pass_mode` range/min-only/max-only, stimulus PSU_MSO vs AWG, n) **Save Version overlay** writes `#Test_Database/.../{Operator}/Version_N/_manifest/test_params.yaml` (`vcc_plan` alias of `vcc_grid`, merged `vcc_list`, `pass_mode`, `sample_size`, `stable_eps_A`). PSU_MSO hides Freq/Amp. Not xyflow. Visual tables still write pass_mode on the limits table.
5. `python -m ate.core.check_logic_dc` (also `check_add_test`, `check_family_load`). Visa-free Path B catalog: `python -m ate.core.check_logic_dc_sim` (the 11 CONFIRMED; overlay one VCC; `stable_eps_A` null = NON_TIGHT; G07 VOH SKIP; RS164 sequential 2^n SKIP). CONFIRMED Path B `TestSpec.run` walk (`_confirmed_sim_sweep_ok`) for GT34, G97, G126, G08, G07, G14, G32, GT08, GT32, G125, RS164 -- `fixture_modes.SIM.tests` if present, else LOGIC `enabled_tests`. RS164 Path B gate ids stay OFF (sequential, not 2^n). Import-format alias `ate/tests/logic/dc.py` is the same runner (not a second fork). RS1G123 / RS1G74 are PARKED UNCONFIRMED archive -- not in the mandatory SIM set; missing yaml does not block green; FAIL if treated as gate 2^n. Next-wave G00/G02/G04/G86/2G08/2G32 UNCONFIRMED -- numbers HOLD. Timeout SIM raises. **Not a reproduce claim.**

DEMO on Run walks ticked tests with mock numbers and writes `sessions/` JSON. It does **not** stamp the lab xlsx as PASS. DEMO is not PSU->settle->measure. START.bat is still how the zip console comes up.

## HUMAN + real instruments -- required to reproduce

Reproduce Path B DC only with a human, Open Session, and live PSU + DMM + AWG wired to the DUT. Launch **START.bat**, then Continue prompts (wire_map + ICC / II / IOZ recable) -- follow them. Fixture text is `fixture_modes.LOGIC.checklist` on the part yaml (Setup/Run checklist), not a second invented wiring table.

After each PSU VCC switch and pin force: **PSU -> settle -> measure**. Voltage must hold `stable_n` inside `stable_eps_V`. Current: if `stable_eps_A` is set, hold `stable_n` inside **`stable_eps_A`** (amps) or **FAIL** on timeout. If `stable_eps_A` is null/missing, the runner does **not** reuse `stable_eps_V`; it waits `settle_s` once, measures, and tags `settle=NON_TIGHT` (not greenable as tight-settle). Tight-settle **claims** without `stable_eps_A` stay FAIL-closed. If the DMM never settles before `settle_timeout_s` on the tight path, the step **FAIL**s. Do not treat a timed-out last reading as PASS.

| Id | Sense (from `logic_dc.py` INSTRUMENT_SENSE) | Notes |
|----|-----------------------------------------------|-------|
| ICC | DMM-on-VCC (DMM in series with PSU CH1 / DUT VCC) | All `2^n` corners. Null `stable_eps_A` = NON_TIGHT. Overlay amps for tight settle-to-stable |
| ΔICC | DMM-on-VCC; one input at VCC-offset or ICCT voltage, others at rail | 97/126: `recipe.delta_offset_v` 0.6. 34: ICCT 500uA @5.5V one_in@3.4 (`dc_limits.ICCT_uA`) -- do not invent 0.6 |
| II | DMM in series with the swept input; force VI | Per input, VI=0 and VI=max |
| VTH / VIH / VIL | Force unused ties from truth_table; DMM sense V(Y) | 97 Schmitt = VT+/VT- (range). 126 = VIH min_only / VIL max_only. 34 CONFIRMED: per-VCC limits from `vcc_grid`; `recipe.search` / `threshold_search` (limit-scaled first step, on-hit skip, no reverse) |
| VOH | Force Y=H from truth_table; DMM sense V(Y); IOH via PSU CH2 | Loaded rows from CONFIRMED `dc_limits.VOH.loads` expansion (band onto merged `vcc_list`; named high-load at card VCC) or campaign `voh_table` (97/126/34). Judge **VOH >= min** (`min_only`). Open-drain SKIP. |
| VOL | Force Y=L from truth_table; DMM sense V(Y); IOL via PSU CH2 | Loaded rows from CONFIRMED `dc_limits.VOL.loads` expansion or campaign `vol_table`. Judge **VOL <= max** (`max_only`) |
| IOZ | Only if OE exists. OE inactive; DMM in series with Y; PSU CH2 force Vout | 126: yes. 97 `oe: none`: do **not** tick ioz |

PSU CH1 is VCC. PSU CH2 is Y-load/vref (VOH sink rail 0V, VOL source rail = VCC -- fixture, not a datasheet Vref) when a `voh_table`/`vol_table` exists (97/126/34 CONFIRMED -- pin Y, not a new net). RS1G97 pin C is PSU CH3 (checklist: AWG CH1=A CH2=B). RS1G126: AWG CH1=A CH2=OE; no C. RS1GT34 CONFIRMED PSU_MSO: PSU CH1=VCC, PSU CH2=Y-load for `voh`/`vol`, PSU CH3=A; DMM/SCOPE on Y; NC not wired; **do not invent AWG Freq/Amp**.

## Customise Parameters (`vcc_grid`)

Setup **Logic DC recipe** -- Customise Parameters (no xyflow):

1. **FIXED POINTS** chips -- add/remove VCC; each chip has editable VIH min / VIL max.
2. **RANGE SWEEPS** -- Add range start/stop/step (default 0.1); optional label; **same** VIH/VIL limits for every stepped VCC in that band. Range steps inherit band limits -- they are not stored as a fixed-point row.
3. Preview merged `vcc_list` before START.
4. Stimulus: **PSU_MSO** (hides Freq/Amp; omit Hz/V -- do not invent) vs **AWG**.
5. n (`sample_size`); pass_mode VIH=`min_only` VIL=`max_only`.
6. **Save Version overlay** writes campaign `_manifest/test_params.yaml` only (not Save product_model).

Runner merges `fixed_points` + `ranges` -> `vcc_list`. Per-VCC VIH/VIL from the owning fixed point or range. Exact-VCC fixed points overwrite range-step ownership.

YAML `vcc_grid.status` CONFIRMED is Datasheet-signed (97/126/34 and the 8 SoT SKUs: 08/07/14/32/GT08/GT32/G125/RS164). Overlay edits cannot promote unsigned SKUs. New SKUs stay UNCONFIRMED -- fail-closed for numbers green.

Do not invent extra IOH/IOL rows. Path B prefers CONFIRMED `dc_limits.VOH/VOL.loads` (formula **VCC-0.1** only). Campaign Ariff `voh_table`/`vol_table` stay on 08/32/GT08/GT32 (Path A). G07 campaign `vol_table` stays 4 extract rows; SoT 0.1mA/24mA live in `dc_limits.VOL` only.

## Scale to other boards / parts

No per-board VOH script. Path B loads come from that SKU's CONFIRMED `dc_limits.VOH/VOL.loads` (expand onto merged `vcc_list`; formula **VCC-0.1** only). Stimulus uses truth_table all-high (VOH) / all-low (VOL) when that vector exists. Add a SKU: part yaml + limits + product_model; do not fork `logic_dc.py`. Dual-channel Continue is **2Gxx only** -- 1Gxx cards leave `recipe.dual_channel_continue` off.

Optional `product_model.live` (sibling of `data_paths`, not a data_paths key) records a bench session against golden_auto / `sessions/`. Do not copy LIVE measured numbers onto other SKUs. Do not invent VOL.

## Dual-channel Continue (future 2Gxx)

OpAmp dual Continue is reused as DATA, not hardcoded OpAmp. See `docs/LOGIC_DC_DUAL_CHANNEL.md`.

`recipe.dual_channel_continue` + `recipe.channels: [CHA, CHB]` -- operator Continue CHA then CHB. Path B TestSpecs stay registered `dual_channel=False`; the runner ORs the recipe flag at run (does not wrap `TestSpec.run`). 1Gxx cards leave the flag off. No fake 2G part YAML without a Datasheet card.

## Excel path -- never invent cells

**Split:** two books, two jobs.

- **auto** / **golden_auto** = the chosen campaign Version `#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/workbook/`. `workbook_policy.auto` / `golden_auto: one_per_version_overwrite`. Continue / Open Session / START / Fill Excel always overwrite-in-place **that** book. JSON->Excel from card-backed field ids only. CSV sidecar `sessions/csv/{sheet}.csv` + fill log `sessions/path_b_write.json` overwrite with the same auto dest. Plots as already specified. Setup shows CONFIRMED/UNCONFIRMED.
- **pretty** / **ultimate_manual** = a separate jot / pretty workbook. `workbook_policy.pretty` / `ultimate_manual: never_auto_write`. pretty never auto. NEVER the auto target (xlsx or CSV). Do not write Path B auto runs into pretty or ultimate. Do not invent columns.

Same session always overwrites the same golden_auto xlsx. Never an orphan second Version book (`_filled.xlsx` or another golden name). If Excel has the golden file locked, Fill Excel **FAIL**s (orphan) -- do not save a second path. If the auto dest is the jot / pretty book, Fill Excel **FAIL**s (`ultimate`).

Campaign tree (same copy-ready Version folder as above):

```
#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/
  START.bat
  report.pdf                # latest STS (pass/fail vs limits; never invent numbers)
  workbook/                 # golden_auto lab xlsx (overwrite-in-place)
  workbook/*_datapoints.csv # full datapoints beside golden_auto
  _manifest/sheet_map.yaml  # OpAmp / imported VOX paste anchors
  _manifest/test_params.yaml
  sessions/report.json
  sessions/datalog.md
  sessions/csv/             # Path B auto CSV (pretty never auto)
  sessions/path_b_write.json
  {test}/DUT_n/records/
```

Record path after a run is still: that golden_auto workbook + `*_datapoints.csv` sidecar + `sessions/csv/` + `sessions/report.json` + `{test}/DUT_n/records/` + STS datalog + Version `report.pdf`. The jot book is outside this auto path. pretty never auto.

### Path B (RS1G97 / RS1G126 / RS1GT34)

`product_model.excel_plots` binds card-backed series only. Headers come from Path B runner row keys. Regex only **detects** plottable series -- it does not invent columns or G16 paste cells.

Setup sheet: `wire_map`, `vcc_list` / `vcc_grid`, `pass_mode`, CONFIRMED/UNCONFIRMED status.

Per enabled Path B test tab (`VTH` / `Icc` / `DeltaICC` / `II` / `VOH` / `VOL` / `IOZ`) scales with DUT count and VCC plan. IOZ tab only if OE is on the card. DeltaICC tab only if `delta_icc` is enabled+mapped.

Auto plots when series data exists (from those headers):

- VIH/VIL measured vs Vcc + limit lines (`min_only` / `max_only`)
- VT+/VT- vs Vcc (+ ΔVT if Schmitt)
- ICC vs Vcc (`2^n` corners)
- ΔICC vs Vcc only if enabled+mapped
- II vs Vcc per pin
- VOH vs IOH @ Vcc (limit min); VOL vs IOL @ Vcc (limit max)
- IOZ only if OE on card

Series ids only: `vih_vs_vcc`, `vil_vs_vcc`, `icc_vs_vcc`, `voh_at_ioh`, `vol_at_iol`, `ii_vs_vcc`, `ioz_vs_vcc` if OE; `vtplus_vs_vcc` / `vtminus_vs_vcc` / `dvt_vs_vcc` if Schmitt; `delta_icc_vs_vcc` only if enabled+mapped.

**Results -> Fill Excel numbers** on Path B overwrites the one Version **auto** / **golden_auto** xlsx (`write_path_b_workbook`) plus `sessions/csv/` and `sessions/path_b_write.json`. Full `*_datapoints.csv` is also written beside the golden xlsx. Continue / Open Session bind fill/plot to that Version path only. pretty never auto. `check_logic_dc` FAIL-closes an auto write path that equals **pretty** / **ultimate_manual**, an orphan second Version xlsx, invented columns, or an enabled test with series data but no `excel_plots` binding.

RS1GT34 `excel_plots.status` is **CONFIRMED** (Jian Hong 2026-09-18). `delta_icc_vs_vcc` is bound (ICCT mapped). No `ioz_vs_vcc` (`oe: none`). That status gate is not a bench green.

### OpAmp / imported VOX (not Path B)

**Results -> Fill Excel numbers** writes `sheet_map` `tests.<key>.paste.values` from living `sessions/report.json`. Photos use `paste.photos`. Do **not** invent Excel cells in this doc, in Python, or in chat.

Paste cells come from, in this order only:

1. That campaign's `_manifest/sheet_map.yaml` (operator-filled from the **live** workbook).
2. Known keys already in `ate/core/campaign_outline.py` **when those sheets exist on the imported xlsx** -- do not add corners that are not on the sheet:
   - Logic VOX sheet: `VOH_4p5V` DUT list `G16` / `H16` / `I16`; `VOL_4p5V` `G25` / `H25` / `I25`
   - Logic ICC sheet (not RS0204 `Icc` grid): `ICC_uA` `D10`
3. Import may stub `FILL_ME`. A human fills real cells from the tracking xlsx. A filled map is not overwritten without a `.bak_*` backup.

Path B does **not** mint those G16 / D10 cells. The CONFIRMED 97/126 VOH/VOL Full grid (100uA + 4/8/16/24/32mA ids in part yaml) is **limits + runner + excel_plots**, not a license to mint new paste cells here. Map coverage is Setup **Map coverage**.

## Log path

| What | Where |
|------|--------|
| Living latest merge | `{Version_N}/sessions/report.json` |
| Latest STS PDF | `{Version_N}/report.pdf` (overwrite after Version run; Pass criteria / How met from session min/max/value -- never invent pass numbers) |
| Full START snapshot | `sessions/session_*.json` |
| STS datalog | Results **Export STS datalog** -> `sessions/datalog.md` + `.html` + `.pdf` (also `sessions/report.pdf`) |
| Golden CSV sidecar | `workbook/*_datapoints.csv` (full datapoints beside golden_auto overwrite; pretty never auto) |
| Per-step history | `{test_key}/DUT_n/records/{test_id}_{timestamp}.json` (append-only; never overwrite) |
| FAIL attach | `{test}/DUT_n/` (scope PNG / phone photo from Continue) |
| Path B auto CSV | `sessions/csv/{sheet}.csv` (overwrite-in-place with golden_auto; pretty never auto) |
| Path B fill log | `sessions/path_b_write.json` (overwrite-in-place) |

Never dump the RUN-IC catalog into `#Test_Database`. Delete on Results **Run ledger** removes a session JSON only -- never the Version folder or workbook xlsx.

## Console

Zip operators: `START.bat` (from `ATE_Console_Try_*.zip` or the copy-ready Version folder). Clone PCs: `run_ate_app.bat`.

- UI: `http://127.0.0.1:5174`
- Worker JSON-RPC: `http://127.0.0.1:8766` (not 8765)
- After `git pull` / zip refresh: **Ctrl+F5** (`app.js?v=20260918logicdc17`)
- After `ate/tests/**` / worker changes: idle-restart worker (`restart_ate_worker.bat`), not mid-run, then Ctrl+F5

Pick a **person** (not All) -> Apply campaign -> Discover -> Open Session -> tick tests -> START.

## Human-test checklist -- RS1G97 + RS1G126 (Path B)

Short. Same Path B runner. Tick only DC ids below (97 has no IOZ; 126 keeps ten/tdis as AC -- do not treat them as this DC list). START.bat first.

**Both parts**

1. Console up via **START.bat** (5174 / 8766). Person selected. Campaign `#Test_Database/Logic/RS1G97/...` or `.../RS1G126/...` applied.
2. Discover. **Open Session** (PSU + DMM + AWG present; DMM required at run for these ids).
3. Run fixture checklist (part yaml `fixture_modes.LOGIC.checklist`). Wire DMM+PSU+AWG to **wire_map** Continue (CONFIRMED pins + pin_drive only). Human Continue after verify. Recable when ICC series-VCC vs II series-input vs IOZ series-Y vs VOH/VOL DMM-on-Y.
4. Tick Path B DC: `input_threshold` (and/or `vth`), `icc`, `delta_icc`, `ii`, `voh`, `vol`. 126 also tick `ioz`. 97 must **not** tick `ioz` / `ioff`.
5. START (not DEMO). Confirm an unstable DMM **settle timeout hard-FAIL**s (RuntimeError / FAIL) when `stable_eps_A` is grounded, not a last-reading PASS. Recipe timeout 2.0 s. Null `stable_eps_A` is NON_TIGHT (wait `settle_s` once); do not invent uA. Tight-settle claims stay FAIL-closed until overlay/panel sets `stable_eps_A`.
6. On a stable bench: Results / `report.json` -- **VOH >= min** vs CONFIRMED `voh_table` / limits (`min_only`); **VOL <= max** vs CONFIRMED `vol_table` (`max_only`). Do not invent extra loads. After run, Continue shows save paths (`workbook/` + `sessions/report.json` + STS datalog + `{test}/DUT_n/records/`). On FAIL, attach photo to `{test}/DUT_n/`.
7. Fill Excel: Path B overwrites the Version **auto** / **golden_auto** xlsx (`excel_plots` / `auto: one_per_version_overwrite`). pretty never auto. Never write **pretty** / **ultimate_manual**. Never an orphan second Version book. Imported VOX still uses sheet_map / campaign_outline (above). Export STS if needed. No Verify PASS claim from this checklist.

**RS1G97 extra**

- Schmitt: VT+ / VT- / HYST = range. C on PSU CH3. `oe: none`.
- ICC corners = 8 (A,B,C).

**RS1G126 extra**

- VIH min_only / VIL max_only. OE active high. IOZ when OE inactive (data don't-care; Vout sweep per recipe `ioz_vcc_list` / `ioz_vout_list` already on the card -- do not invent).
- ICC corners = 4 (A+OE).

**RS1GT34 extra (CONFIRMED Jian Hong 2026-09-18 -- not a bench green)**

- Console up via **START.bat**. Campaign `#Test_Database/Logic/RS1GT34/...`. Owner note: Chun Tak / Core AE OK.
- n=1. Y=A. Not Schmitt. `oe: none` -- do **not** tick ioz / ioff (Ioff is VCC=0; not IOZ).
- Stimulus **PSU_MSO** -- hide Freq/Amp. PSU CH1=VCC, PSU CH2=Y-load for `voh`/`vol` (pin Y), PSU CH3=A, DMM/SCOPE Y. Do not invent AWG nets.
- Tick Path B DC: `input_threshold`, `icc`, `ii`, `voh`, `vol`, `delta_icc`. `delta_icc` ON: ICCT 500uA @5.5V one_in@3.4. Do not invent `delta_offset_v=0.6`.
- `input_threshold` uses `recipe.search` / `threshold_search.py`: limit-scaled first step (largest ladder step <= card |limit|), on-hit skip rest of walk, no reverse in a stage (VIH arm 0 up; VIL arm VCC down).
- VOH/VOL from CONFIRMED `dc_limits` loads / `voh_table`/`vol_table` (100uA on merged `vcc_list`; high-load only at 2.0/3.3/4.5/5.0/5.5). Judge **VOH >= min** (`min_only`) / **VOL <= max** (`max_only`).
- JH room 2026-09-18 **VOH LIVE SUCCESS** (`min_only`). Board still wired for VOH. VOL needs board change -- **do not invent VOL**. Recorded in `product_model.live` (golden_auto Version `workbook/` + `sessions/`). Not a Verify PASS. Not bench-green for other tests or other SKUs.

**GT34 VOL board-change resume (LIVE -- tomorrow)**

1. START.bat. Person selected. Campaign `#Test_Database/Logic/RS1GT34/...`. Open Session.
2. Recable PSU CH2 Y-load: VOH sink was 0V; VOL source rail = VCC. Keep CH1=VCC, CH3=A, DMM/SCOPE on Y. PSU_MSO -- no AWG Freq/Amp.
3. Human Continue after wire_map verify. Tick `vol`. Judge **VOL <= max** (`max_only`). Do not invent VOL measured. `live.vol` stays NOT_RUN until this session.
4. START (not DEMO). Fill golden_auto only. Do not write pretty. Do not copy VOH LIVE numbers onto VOL or other SKUs.

See `HANDOVER.md` / `docs/LOGIC_DC_HANDOVER.md`.

| IOH | VCC | min | measured | result |
| -8 mA | 2.0 | 1.6 | 1.7089 | PASS |
| -24 mA | 3.3 | 2.5 | 2.8968 | PASS |
| -32 mA | 4.5 | 3.8 | 4.0695 | PASS |
| -32 mA | 5.0 | 4.2 | 4.5867 | PASS |
| -32 mA | 5.5 | 4.8 | 5.0992 | PASS |
- II: +/-1uA +25C judged (`II_uA`); Full +/-5uA documented (`II_FULL_uA`, no run-judge). ICC: 1uA +25C judged (`ICC_uA`); Full 10uA documented (`ICC_FULL_uA`).
- `vcc_grid` CONFIRMED: fixed 2.0 (VIH>=1.0 VIL<=0.3), 3.3 (VIH>=1.5 VIL<=0.55); range 4.5-5.5 step 0.1 (VIH>=2.0 VIL<=0.8). Preview merged `vcc_list` before START.
- Excel: auto overwrite Version; pretty never auto.
- ICC corners = 2 (A). START.bat first. No Verify PASS.

**JH room CONFIRM (grounded fields only -- 2026-09-17; not a bench green)**

Eight overnight models are **CONFIRMED** for grounded extract/card fields (truth_table / pins / isolation / oe / open_drain / sequential), for `vcc_grid` / `vcc_plan` VIH/VIL (G14 VT+/-), and for push-pull/three-state `dc_limits.VOH/VOL` copied from signed card / box SoT (Jian Hong 2026-09-18). Do not invent extra rows. Fail-closed remain: `stable_eps_A` null, retention MAX if missing, RS164 Ioff+ICCT ABSENT (delta_icc off), G07 VOH N_A, G125 IOZ @3.6V UNSURE this turn, unsigned ICCT. GT34 already CONFIRMED (2026-09-18); `dc_limits.VOH/VOL.loads` now match the attached SoT. STS latest `report.pdf` copies measured rows with Pass criteria / How met (never invent pass numbers). Dual Excel: golden_auto overwrite + pretty never auto; `sessions/csv/` + `sessions/path_b_write.json`.

1. RS1G08 AND-2 other=H; no IOZ; keep AWG pin_drive + SOT23 campaign; no Path B excel_lock. VIH/VIL four CMOS bands CONFIRMED. `dc_limits.VOH/VOL` CONFIRMED 6-load SoT (0.1mA band + named high-load incl 24mA). Do not copy extract 9.2 over Ariff campaign `voh_table`.
2. RS1G07 open-drain: do not tick voh (VOH N_A). Y=Z is not IOZ. Campaign `vol_table` stays 4 extract IOL rows. `dc_limits.VOL` CONFIRMED SoT 6-load copy including 0.1mA and 24mA -- copy, not invent. VIH/VIL same CMOS bands CONFIRMED from SoT.
3. RS1G14 Schmitt VT+/- range; tick `vth` (not plain VIH/VIL). VT+/- / dVT CONFIRMED. Enable voh/vol (push_pull + CONFIRMED SoT tables). Data retention MAX stays UNSURE (PDF MIN 1.5 only).
4. RS1G32 OR-2 other=L. RS1GT08/RS1GT32 TTL VCC 2.0-5.5; ICCT one_in@3.4 (not 0.6). VOH/VOL CONFIRMED SoT 6-load (TTL 0.1mA band + named 8/24/32mA).
5. RS1G125 OE active-L -> tick ioz when OE inactive only (`recipe.ioz_when: oe_inactive`; force OE=H, never active L). Enable voh/vol (three_state + CONFIRMED SoT). RS164 sequential_shift_register -- do not tick Path B gate 2^n; VOH/VOL stay UNCONFIRMED (do not expand).
**Dropped / archive (not Path B scale):** RS1G123 / RS1G74 stay optional **PARKED** UNCONFIRMED stubs. Missing yaml does not block green. Do not invent VT+/- or gate 2^n. If yaml is present: Path B gate 2^n stay off; 74 runner `sequential_dff_clr_pre` (alias `sequential_dff`); 123 runner `sequential_monostable_rc`; 123 ICCT ABSENT; schmitt false. `check_logic_dc` FAILs if treated as gate 2^n.

**Next-wave UNCONFIRMED (numbers HOLD; no CONFIRM; `ate_ds_extract/models` not in workspace):** All six ICCT ABSENT -- delta_icc from `delta_icc_uA` only (do not invent ICCT). RS1G00 NAND other=H invert; oe none; IOZ OFF. RS1G02 NOR other=L invert, TTL-style VIH/VIL (not G08 CMOS). RS1G04 inverter n=1, NC not OE, IOZ OFF. RS1G86 XOR dual isolation track+invert; VIL 0.20*VCC at 1.65-1.95 from card. RS2G08 / RS2G32 dual AND/OR with `recipe.dual_channel_continue` CHA then CHB. Invent OE/IOZ/ICCT or skip CHA->CHB FAILs.

No Verify PASS.

## Ready vs Not ready (SIM only -- not bench green)

`python -m ate.core.check_logic_dc_sim` on the **11 CONFIRMED** Logic SKUs (skip OpAmp/LDO/Switch/Level). Visa-free. Fail-closed on invent / `stable_eps_A` null / glyph gaps. Dual-channel Continue path is ready. RS2G08 / RS2G32 are UNCONFIRMED stubs (numbers HOLD). Extra `rs2g*.yaml` without a Datasheet card stays forbidden.

| Part | SIM | Live | Gaps / blocked |
|------|-----|------|----------------|
| RS1GT34 | SIM green | VOH LIVE_PASS; VOL NOT_RUN | VOL needs board change -- do not invent VOL. Not bench green for other ids |
| RS1G08 | SIM green | none | excel_lock OFF; `stable_eps_A` null NON_TIGHT |
| RS1G07 | SIM green | none | VOH SKIP N_A -- do not invent VOH. VOL live still NOT_RUN |
| RS1G14 | SIM green | none | data retention MAX UNSURE |
| RS1G32 | SIM green | none | `stable_eps_A` null |
| RS1GT08 | SIM green | none | TTL ICCT 3.4 -- do not invent 0.6 |
| RS1GT32 | SIM green | none | TTL ICCT 3.4 -- do not invent 0.6 |
| RS1G125 | SIM green | none | IOZ @3.6V UNSURE this turn |
| RS1G97 | SIM green | none | CONFIRMED status gate only -- not a bench green |
| RS1G126 | SIM green | none | CONFIRMED status gate only -- not a bench green |
| RS164 | SIM skip (sequential) | none | not combinational 2^n; VOH/VOL UNCONFIRMED; Ioff+ICCT ABSENT |
| RS1G123 | PARKED | none | JH dropped. UNCONFIRMED archive. Sequential -- FAIL if treated as gate 2^n |
| RS1G74 | PARKED | none | JH dropped. UNCONFIRMED archive. Sequential -- FAIL if treated as gate 2^n |
| RS1G00 | UNCONFIRMED (numbers HOLD) | none | NAND other=H invert; ICCT ABSENT; no invent OE/IOZ |
| RS1G02 | UNCONFIRMED (numbers HOLD) | none | NOR other=L invert; TTL-style VIH/VIL -- not G08 CMOS |
| RS1G04 | UNCONFIRMED (numbers HOLD) | none | inverter n=1; NC not OE; IOZ OFF |
| RS1G86 | UNCONFIRMED (numbers HOLD) | none | XOR track+invert; VIL 0.20*VCC @1.65-1.95 from card |
| RS2G08 | UNCONFIRMED (numbers HOLD) | none | dual AND; CHA then CHB Continue; no invent OE/IOZ |
| RS2G32 | UNCONFIRMED (numbers HOLD) | none | dual OR; CHA then CHB Continue; no invent OE/IOZ |

**Next SKU (not this turn -- no invent extra cards)**

| Part | Path B | Why |
|------|--------|-----|
| RS74AUP1G07 | Not ready | wait sample; no Datasheet card |
| RS1GT32D | Not Path B | Ariff Path A campaign (not RS1GT32XC5) |
| RS29511 | Not Path B | Soo Logic suite |
| extra 2Gxx | Not ready | extra `rs2g*.yaml` without Datasheet card forbidden |

**Dropped / archive:** RS1G123, RS1G74 -- PARKED UNCONFIRMED; optional; not in SIM mandatory set; FAIL if treated as gate 2^n.

Skipped non-logic Reference (OpAmp/LDO/Switch/Level): RS0204, RS0302, RS12X, RS22X, RS62X, RS72X, RS82X, RS2323, RS3213, RS32X.
