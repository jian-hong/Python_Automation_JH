# Path B Logic DC -- operator

**PR #5 HEAD SHA:** `87960a7`

This file is the bench/operator map. Writer/import format stays in `docs/LOGIC_DC.md`. Verify is a separate agent. This page is **not** a reproduce claim and does **not** claim Verify PASS / bench green.

Settle loop (this PR): recipe `settle_s=0.05`, `stable_n=3`, `stable_eps_V=0.005`, `settle_timeout_s=2.0`. Voltage (VOH/VOL/threshold) waits eps/N vs `stable_eps_V`. Current (ICC / ΔICC / II / IOZ) uses `stable_eps_A` only -- 97/126 default is **null**. Do **not** reuse `stable_eps_V` as amps (0.005 V would be a 5 mA window). Do **not** invent a uA epsilon.

- Tight settle-to-stable (`stable_eps_A` set via panel / `_manifest/test_params.yaml` overlay): eps/N + hard timeout. Timeout raises `RuntimeError` / FAIL. It does **not** return the last reading.
- Null `stable_eps_A`: tight-settle **claims** stay FAIL-closed. Honest path waits `settle_s` once then measures and tags `settle=NON_TIGHT` (not greenable as tight-settle).
- Ground `stable_eps_A` (amps) on the Logic DC panel overlay before claiming current settle-to-stable.

`check_logic_dc` also FAIL-closes **enabled-but-unrunnable** ids: every part `enabled_tests` id must have a registered `TestSpec` with callable `run` (no stub). Enabled `voh`/`vol` without `voh_table`/`vol_table` rows FAIL the same gate. Enabled 97/126 tests with empty `wire_map` or missing `data_paths` FAIL too. Never invent nets.

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
5. `python -m ate.core.check_logic_dc` (also `check_add_test`, `check_family_load`). Visa-free SIM: rs1g08 ICC corners=4, rs1g97=8, rs1g126 A+OE=4, rs1g07 open-drain n=1=2. Timeout SIM raises. **Not a reproduce claim.**

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
| VOH | Force Y=H from truth_table; DMM sense V(Y); IOH via PSU CH2 | Loaded rows from `voh_table` (97/126/34 CONFIRMED). Judge **VOH >= min** (`min_only`) |
| VOL | Force Y=L from truth_table; DMM sense V(Y); IOL via PSU CH2 | Loaded rows from `vol_table` (97/126/34 CONFIRMED). Judge **VOL <= max** (`max_only`) |
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

YAML `vcc_grid.status` CONFIRMED is Datasheet-signed (97/126/34). Overlay edits cannot promote unsigned SKUs. New SKUs stay UNCONFIRMED -- fail-closed for numbers green.

Do not invent extra IOH/IOL rows. Tables live in part yaml + `ate/config/limits/`.

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
- After `git pull` / zip refresh: **Ctrl+F5** (`app.js?v=20260918logicdc14`)
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
- VOH/VOL from CONFIRMED `voh_table`/`vol_table` (100uA on merged `vcc_list`; high-load only at 2.0/3.3/4.5/5.0/5.5). Judge **VOH >= min** (`min_only`) / **VOL <= max** (`max_only`).
- II: +/-1uA +25C judged (`II_uA`); Full +/-5uA documented (`II_FULL_uA`, no run-judge). ICC: 1uA +25C judged (`ICC_uA`); Full 10uA documented (`ICC_FULL_uA`).
- `vcc_grid` CONFIRMED: fixed 2.0 (VIH>=1.0 VIL<=0.3), 3.3 (VIH>=1.5 VIL<=0.55); range 4.5-5.5 step 0.1 (VIH>=2.0 VIL<=0.8). Preview merged `vcc_list` before START.
- Excel: auto overwrite Version; pretty never auto.
- ICC corners = 2 (A). START.bat first. No Verify PASS.

**JH room CONFIRM (grounded fields only -- 2026-09-17; not a bench green)**

Eight overnight DRAFT models are **CONFIRMED** for grounded extract/card fields (truth_table / pins / isolation / oe / open_drain / sequential). `vcc_grid` / `vcc_plan` 9.1 VIH/VIL stay **UNSURE** (PDF table image -- do not invent). Glyph-missing uA/mA rows stay omitted. GT34 already CONFIRMED (2026-09-18). STS latest `report.pdf` copies measured rows with Pass criteria / How met (never invent pass numbers). Dual Excel: golden_auto overwrite + pretty never auto; `sessions/csv/` + `sessions/path_b_write.json`.

1. RS1G08 AND-2 other=H; no IOZ; keep AWG pin_drive + SOT23 campaign; no Path B excel_lock. VIH/VIL 9.1 PDF image -- UNSURE. Do not copy extract 9.2 over Ariff voh_table. Light-load 100uA and IOH -24mA VCC glyph-missing -- omitted.
2. RS1G07 open-drain: do not tick voh; Y=Z is not IOZ. VOL = extract-explicit IOL only (4/8/16/32mA, CONFIRMED). Do not invent 100uA or 24mA VCC.
3. RS1G14 Schmitt VT+/- range; tick `vth` (not plain VIH/VIL). VT grid stays in yaml; vcc_grid.status UNSURE until extract-signed.
4. RS1G32 OR-2 other=L. RS1GT08/RS1GT32 TTL VCC 2.0-5.5; ICCT one_in@3.4 (not 0.6).
5. RS1G125 OE active-L -> tick ioz when OE inactive only (`recipe.ioz_when: oe_inactive`; force OE=H, never active L). RS164 sequential_shift_register -- do not tick Path B gate 2^n.

No Verify PASS.
