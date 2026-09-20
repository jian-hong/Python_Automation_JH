# STANDARD FORMAT -- write / import a test (live UI)

Live console only (`ate/` + worker **8766** + UI **5174**). Vibe-coder map: `AGENTS.md`. Plug-in slots: `docs/ATE_PLUGIN.md`. UI chrome: `ate/ui/web/UI_CONTRACT.md`. Path B TestSpecs stay physics bodies. Do not add wizard-Python, xyflow, a second runner, or scrape en.run-ic.com.

New RS1Gxx (2-input, 3-input, N-input, with/without OE) should not need a forked `logic_dc.py`.

Operator bench (DEMO/SIM vs HUMAN+instruments, Excel/log paths, 97/126 checklist): `docs/LOGIC_DC_OPERATOR.md`. AE/FAE last-day map: `docs/LOGIC_DC_HANDOVER.md` (also repo-root `HANDOVER.md`). Dual-channel Continue (2Gxx): `docs/LOGIC_DC_DUAL_CHANNEL.md`. DEMO/SIM and `check_logic_dc` are **not** a reproduce claim.

## Which path (labels match Setup)

Stop at the first row that holds. Same three paths as `AGENTS.md` + `docs/ATE_PLUGIN.md`.

| Path | When | Live UI (Setup tab) | Check |
|------|------|---------------------|-------|
| **A -- new body** | New physics (not already `input_threshold` / `icc` / ...) | `register(TestSpec)` then idle-restart worker. Checkbox appears under **Test program** | `check_family_load` |
| **B -- Logic DC recipe** | Same DC ids, new SKU | **Logic DC recipe** panel (truth table, `logic_inputs`, `vcc_list`, limits + `pass_mode`) + **Test program** ticks | `check_logic_dc`, `check_add_test` |
| **C -- Detect / Wrap** | Golden `test_*` already exists | **Detected tests (golden + ate/tests)** -> **Wrap + enable on part** | `check_test_detect` |

Path A template: `register(TestSpec)` in `AGENTS.md`. Path C: AST only; `input()` stays blocked. Wrap goldens via existing `seelim_dc` / `ariff_dc` locators -- do not copy See Lim limits into YAML.

Setup **Test program** shows this table in `#add-test-format` (always visible). `pass_mode` is editable on **Test program** (per spec) and on **Logic DC recipe** (limits table). **Save pass_mode overlay** / **Save Version overlay** writes `_manifest/test_params.yaml`. Missing min/max stay **unspec** unless `fail-open` (then fail). Never fake PASS.

## Add RS1Gxx with only part + limits + truth (Path B)

1. `ate/config/parts/<key>.yaml` -- `enabled_tests` + `product_model` (below).
2. `ate/config/limits/<key>.yaml` -- datasheet min/max + `pass_mode`. Numbers from local Reference PDF extract only.
3. Campaign: Setup **Create folders + open** / Apply. Optional Version overlay `_manifest/test_params.yaml`.
4. Idle-restart worker. Ctrl+F5. Tick tests. START (or DEMO -- DEMO does not call TestSpec.run).

Do not add a Tags or Users folder axis. Do not fork Python per SKU.

### `product_model` keys

```yaml
product_model:
  schmitt: false          # true = VT+/VT- (range); false = VIH/VIL
  oe: none                # none | {pin: OE, active: high|low}
  logic_inputs: [A, B]    # corners = 2^n (OE extra for ICC when present)
  vcc_list: [1.65, 5.0]   # alias: vcc_sweep_list
  vcc_grid:               # Customise Parameters (overlay or YAML). Merges to vcc_list.
    stimulus: PSU_MSO     # PSU_MSO hides Freq/Amp; AWG keeps them
    pass_mode: {VIH: min_only, VIL: max_only}
    fixed_points: [{vcc: 2.0, VIH_min_V: 1.0, VIL_max_V: 0.3}]
    ranges: [{start: 4.5, stop: 5.5, step: 0.1, VIH_min_V: 2.0, VIL_max_V: 0.8, label: optional}]
    status: CONFIRMED       # Datasheet-signed; UNCONFIRMED is not greenable
  pins:
    - {name: A, role: input}
    - {name: Y, role: output}
  truth_table:
    status: UNCONFIRMED   # Datasheet-signed is the only greenable token
    rows:
      - {A: H, B: H, Y: H}
      - {A: L, B: H, Y: L}
  # isolation / threshold_isolation optional -- omitted = derive from truth_table
  # threshold_isolation: [{sweep, hold, y_tracks, status}]
    recipe:
    threshold_step_v: 0.05
    settle_s: 0.3
    stable_eps_V: 0.005
    stable_eps_A: null  # current: null = NON_TIGHT (wait settle_s once); set amps for eps/N; do not invent uA
    delta_offset_v: 0.6   # dICC; omit if datasheet has ICCT one_input_V instead (do not invent 0.6)
    dual_channel_continue: false  # future 2Gxx CHA then CHB Continue; see docs/LOGIC_DC_DUAL_CHANNEL.md
    # channels: [CHA, CHB]  # 2Gxx only; extra rs2g yaml without Datasheet card forbidden
    search:               # optional; missing keeps threshold_step_v walk
      vih: {arm: 0.0, direction: up, no_reverse_in_stage: true}
      vil: {arm: VCC, direction: down, no_reverse_in_stage: true}
      step_ladder_V: [0.5, 0.2, 0.1, 0.05, 0.01]
      on_hit: {skip_rest_of_walk: true, rearm: true, next_smaller_step: true}
  gaps: []                # honest UNSURE / PROVISIONAL notes
  # AE/FAE handoff (97/126/34): wire_map from CONFIRMED pins+pin_drive only.
  # settle_prompt (show wait). data_paths folder templates -- never invent nets/cells.
  # data_paths.csv: sessions/csv/ (auto overwrite with golden_auto; pretty never auto)
  workbook_policy:
    auto: one_per_version_overwrite            # alias of golden_auto
    golden_auto: one_per_version_overwrite      # Version workbook/ overwrite-in-place
    pretty: never_auto_write                  # pretty never auto
    ultimate_manual: never_auto_write          # jot book -- never the auto target
  excel_plots:
    series: [vih_vs_vcc, vil_vs_vcc, icc_vs_vcc, voh_at_ioh, vol_at_iol, ii_vs_vcc]
    # ioz_vs_vcc only if OE; vtplus/vtminus/dvt if Schmitt; delta_icc_vs_vcc if enabled+mapped
    # RS1GT34: status CONFIRMED (Jian Hong 2026-09-18); delta_icc_vs_vcc bound; no ioz
```

Aliases accepted: `logic_dc:` (same mapping as `product_model:`); `vcc_sweep_list`; `threshold_isolation: [{sweep, hold, y_tracks}]`. Shared runner: `ate/tests/logic/logic_dc.py` (import-format alias `ate/tests/logic/dc.py` -- not a second fork).

`pass_mode` on the part yaml (alias `limit_mode`): Schmitt VT+/VT-/hysteresis = `range`; VIH/`VOH` = `min_only`; VIL/VOL/ICC/dICC/II/IOZ = `max_only`.

### What the shared runner derives

- **ICC** -- all `2^n` corners (`logic_inputs`; plus OE when `oe != none`). SIM: 2-input AND = 4, 3-input 97 = 8, 126 A+OE = 4, 07 open-drain n=1 = 2. Sequential (`product_class` / `recipe.runner` contains `sequential`, including RS164 shift-register) is not combinational 2^n -- Path B gate ICC is FAIL-closed. RS1G123 / RS1G74 are dropped/archive optional UNCONFIRMED stubs -- not in the 17 CONFIRMED SIM set; do not invent VT+/- or gate 2^n.
- **VIH/VIL (or VT+/VT-)** -- unused ties from the truth table. Prefer a combo where **Y tracks the swept pin non-inverting**. Invert only when no track combo exists (See Lim RS1G97 algorithm; not a per-SKU hardcoded forever). `isolation_for_run` skips rows marked `PROPOSED` / `HOLD CONFIRM`. Per-VCC VIH min / VIL max come from `vcc_grid` (owning fixed point or range band). Range steps inherit band limits -- never a fixed-point row. `vcc_grid.status` UNCONFIRMED is not greenable. When `recipe.search` is present, `threshold_search.py` walks VIH up / VIL down: limit-scaled first step, on-hit skip rest, no reverse. Missing search keeps `threshold_step_v`.
- **II** -- per input, VI=0 and VI=max.
- **Delta ICC** -- one input at VCC-offset, or at `dc_limits.ICCT_uA.one_input_V` when ICCT is mapped. RS1GT34 enables `delta_icc` from ICCT (500uA @5.5V one_in@3.4). Do not invent `delta_offset_v=0.6`. CMOS cards may map `ICCT_uA.offset_v` (on the card, not invented).
- **IOZ** -- only when OE/3-state exists. Force OE **inactive** only (`ioz_force_vector` / `recipe.ioz_when: oe_inactive`). Do not enable `ioz` / `ioff` on parts with `oe: none`. Open-drain Y=Z is not IOZ.
- **VOH/VOL** -- Path B prefers CONFIRMED `dc_limits.VOH/VOL.loads` (band onto merged `vcc_list`; named high-load at card VCC; formula VCC-0.1 only). Campaign `voh_table`/`vol_table` is fallback (Path A Ariff). Stimulus uses truth_table all-high (VOH) / all-low (VOL) when that vector exists. No per-board VOH script. `check_logic_dc` FAIL-closes if `voh`/`vol` is enabled but the table has no rows. Open-drain skips VOH (open_drain + voh enabled -> FAIL). Unloaded only when the table is absent and the id is not enabled. Optional `product_model.live` (sibling of `data_paths`, not a data_paths key) notes golden_auto / `sessions/` for a bench session. GT34 VOH LIVE_PASS 2026-09-18 min_only; VOL NOT_RUN (board change -- do not invent VOL). Do not copy LIVE numbers onto other SKUs. Dual-channel Continue is 2Gxx only.
- **Settle** -- recipe `settle_s=0.05`, `stable_n=3`, `stable_eps_V=0.005`, `settle_timeout_s=2.0`. Voltage (VOH/VOL/threshold) uses `stable_eps_V`. Current (ICC/ΔICC/II/IOZ) uses `stable_eps_A` only. Never reuse `stable_eps_V` as amps (0.005 V is not a 5 mA window). Do not invent a uA default. If `stable_eps_A` is set (panel / overlay), eps/N + hard timeout FAIL (never last-reading). If null: tight-settle claims stay FAIL-closed; honest path waits `settle_s` once then measures and tags `settle=NON_TIGHT` (not greenable as tight-settle). Not a DC limit.
- **AE/FAE Continue** -- every enabled Path B id surfaces `wire_map` (CONFIRMED pins + `pin_drive` only; never invent nets), stimulus, `settle_prompt` (show wait), measure + `pass_mode`, FAIL attach, then `data_paths` save folders. `check_logic_dc` FAIL-closes empty `wire_map` / missing `data_paths` on 97/126/34.
- **Excel lock** -- `workbook_policy.auto` / `golden_auto: one_per_version_overwrite` on the chosen Version `{Version_N}/workbook/`. Continue / Open Session / START overwrite-in-place that book. CSV sidecar `sessions/csv/{sheet}.csv` + fill log `sessions/path_b_write.json` overwrite with the same auto dest. Full datapoints CSV (`*_datapoints.csv`) is also written beside the golden_auto xlsx. `workbook_policy.pretty` / `ultimate_manual: never_auto_write` -- pretty never auto (xlsx or CSV). The jot/pretty book is never the auto target. Never an orphan second Version book / `_filled.xlsx`. Adaptive Setup + per-test tabs from runner headers (not G16). Auto plots from `excel_plots` when series data exists. `check_logic_dc` FAIL-closes auto dest == pretty/ultimate, a second golden xlsx, invented columns, or enabled series data with no plot binding. RS1GT34 `excel_plots.status` is CONFIRMED. RS1G08 / RS1G07 Path B stubs stay sheet_map (`excel_lock` OFF) until a signed card.
- **STS latest PDF** -- after a Version run, `export_latest_report` overwrites `{Version_N}/report.pdf` from session measurements (Parameter / Unit / Min / Max / Typ / Value / Result / Pass criteria / How met). Existing `sessions/datalog.md|.html|.pdf` stay. Never invent pass numbers.
- **Dual-channel Continue** -- future 2Gxx: `recipe.dual_channel_continue` + `recipe.channels` (CHA then CHB operator Continue). OpAmp dual pattern reused as DATA. See `docs/LOGIC_DC_DUAL_CHANNEL.md`. No fake 2G YAML without a Datasheet card. Schmitt must not collapse to a single VIH.

### TestSpec <-> OOP (Part / Pin / TruthTable / Isolation / Limit / Recipe)

Card field list + OCR bind: `docs/datasheet/card_fields.schema.yaml`. `check_logic_dc` FAIL-closes if a part `enabled_tests` id has no registered TestSpec with callable `run` (enabled-but-unrunnable / stub).

| TestSpec | OOP | Body |
|----------|-----|------|
| `tp` / `ten` / `tdis` | Recipe (AC) | `wraps.py` real wrap of `logic_tests.py` |
| `input_threshold` / `vth` | Pin + TruthTable + Isolation + Recipe | `logic_dc.py` |
| `icc` / `delta_icc` / `ii` | Pin + Recipe + Limit | `logic_dc.py` |
| `voh` / `vol` | Pin + TruthTable + Limit + Recipe | `logic_dc.py` |
| `ioz` | Pin (OE) + Recipe + Limit | `logic_dc.py` (only when `oe != none`) |

See Lim (`seelim_dc.py` locator) and Ariff (`ariff_dc.py` RS1G08-class `voh_load`) are **read-only refs**. Isolation "Y tracks the swept pin" is the See Lim pattern. Do not copy See Lim / Ariff params, vref, or default load rows into Path B 97/126 cards.

OCR: PaddleOCR maps each token onto one card field (assign/edit/delete on the Logic DC panel). Do not install Baidu unless asked.

RS1G97 Datasheet §4 table in part yaml is **CONFIRMED** (Jian Hong 2026-09-17; `RS1G97_card_CONFIRMED.md`). Isolation C-track `A:H B:L` is unlocked and used at run; invert `A:L B:H` stays. RS1G126 truth_table / isolation are the same CONFIRMED gate. RS1GT34 is CONFIRMED (Jian Hong 2026-09-18; `RS1GT34_card_CONFIRMED.md`). RS1G08 / RS1G07 / RS1G14 / RS1G32 / RS1GT08 / RS1GT32 / RS1G125 / RS164 grounded fields (truth/pins/isolation/oe/open_drain/sequential) are **CONFIRMED** (Jian Hong 2026-09-17 room). `vcc_grid` / `vcc_plan` VIH/VIL (G14 VT+/-) are **CONFIRMED** from signed card / box SoT (Jian Hong 2026-09-18) -- copy only; do not invent. Fail-closed stay UNSURE/ABSENT: `stable_eps_A` null, retention MAX if missing, RS164 Ioff+ICCT ABSENT (delta_icc off), G07 VOH N_A, glyph-missing uA/mA rows. G07 VOL 4 extract IOL rows CONFIRMED. G125: IOZ only when OE inactive. RS164: sequential -- gate 2^n/ICC/dICC stay disabled. Never invent 0.6 on GT34; never invent VOH/IOZ on G07. Status gate is not a bench green.

### Version overlay

`#Test_Database/.../{Operator}/Version_N/_manifest/test_params.yaml`

```yaml
vcc_list: [3.3]
vcc_plan: {}    # alias of vcc_grid (Customise Parameters)
vcc_grid: {}
levels: {}      # optional recipe
rails: {}       # optional recipe
stable_eps_A: null  # current settle; set a grounded amp number here, never invent uA in docs
pass_mode:
  ICC_uA: max-only
  VTPLUS_V: range
  VOH_5p0V: min-only
```

Setup **Logic DC** panel:

- JSON editors + **Save product_model** write part yaml via `docs/datasheet/card_fields.schema.yaml` keys (`save_product_model`). Each field is assignable/editable/deletable. Cannot promote status to Datasheet-signed.
- Visual tables + **Save Version overlay** write this campaign file (`save_test_params`). Does not rewrite part yaml.

### `pass_mode` (first-class)

| Mode | Judge | Typical |
|------|-------|---------|
| `range` | min <= value <= max | Schmitt VT+/VT-, VCC |
| `min-only` | value >= min | VIH, VOH |
| `max-only` | value <= max | ICC, dICC, II, IOZ, VOL, VIL |
| `fail-open` | missing min and max -> fail | honest fail-closed when limits not typed |
| `unspec` | never PASS | operator force; also the default when limits missing |

Empty yaml `pass_mode` is inferred from the spec id (`infer` in the panel). Missing limits stay **unspec** unless `fail-open`. Panel + Test program + Results show mode with min/max/result. UNCONFIRMED truth tables cannot green a PASS.

### Pin drive (3+ inputs)

Default: AWG CH1..CH2 then PSU CH2, CH3. **PSU CH1 is VCC. PSU CH2 is Y-load/vref.** Put extra static pins (RS1G97 C) on PSU CH3 in `pin_drive`.

## Checks (the layer you touched)

```
python -m ate.core.check_add_test
python -m ate.core.check_logic_dc
python -m ate.core.check_logic_dc_sim
python -m ate.core.check_family_load
python -m ate.core.check_test_detect
python -m ate.core.check_specs_datalog
python -m ate.core.check_ui_contract
```

A green check that never could fail is not a check. Do not claim bench PASS from SIM. Operator Ready vs Not ready (SIM green / sequential skip / next-SKU gaps) lives in `docs/LOGIC_DC_OPERATOR.md`. `check_logic_dc` fail-closes while a Path B truth_table is UNCONFIRMED; RS1G97 and RS1G126 are CONFIRMED (Jian Hong 2026-09-17) and pass that status gate. RS1GT34 is CONFIRMED (Jian Hong 2026-09-18) and passes the same status gate. G08/G07/G14/G32/GT08/GT32/G125/RS164 grounded truth/pins/isolation are CONFIRMED (Jian Hong 2026-09-17); vcc_grid CONFIRMED from SoT/card (Jian Hong 2026-09-18) unlocks the threshold numbers gate. RS1G123 / RS1G74 are dropped/archive optional UNCONFIRMED stubs (not Path B scale; missing does not block green; do not invent VT+/- / gate 2^n). Enabled `voh`/`vol` without table rows FAIL the same gate. SIM FAIL bars: reverse search, first step > |limit|, auto dest == pretty, invent 0.6, ioz on oe=none, unsigned greenable=False greens PASS. A Path B run that writes the **pretty** / **ultimate_manual** jot book, creates a second orphan Version xlsx, invents columns, or has enabled series data with no `excel_plots` binding, FAIL the same gate.

## Do not

- Fork `ate/tests/logic/logic_dc.py` per SKU
- Call `input()` in a `TestSpec.run`
- Import `Lim.*` / `Ariff.*` / `Soo.*`
- Copy See Lim / Ariff trees into limits yaml
- Enable IOZ/IOFF when `oe` is none
- Invent VOH load tables (copy DRAFT/CONFIRMED card only)
- Invent `delta_offset_v=0.6` for RS1GT34 ICCT
- Invent a uA `stable_eps_A` default, or reuse `stable_eps_V` as amps
- Touch `family_ingest` / `FAMILY_PACKAGES` for a new RS1Gxx
- Invent Excel cells / plot series / a second Version xlsx, or auto-write the pretty / ultimate_manual jot book
- Invent a 2G part YAML without a Datasheet card
- Claim Verify PASS / Datasheet-signed from an UNCONFIRMED table
- Invent RS1G123 / RS1G74 function rows or VOH/VOL loads from glyph-garbled extract
