# STANDARD FORMAT -- write / import a test (live UI)

Live console only (`ate/` + worker **8766** + UI **5174**). Vibe-coder map: `AGENTS.md`. Plug-in slots: `docs/ATE_PLUGIN.md`. UI chrome: `ate/ui/web/UI_CONTRACT.md`. Path B TestSpecs stay physics bodies. Do not add wizard-Python, xyflow, a second runner, or scrape en.run-ic.com.

New RS1Gxx (2-input, 3-input, N-input, with/without OE) should not need a forked `logic_dc.py`.

Operator bench (DEMO/SIM vs HUMAN+instruments, Excel/log paths, 97/126 checklist): `docs/LOGIC_DC_OPERATOR.md`. DEMO/SIM and `check_logic_dc` are **not** a reproduce claim.

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
    status: UNCONFIRMED   # numbers not greenable until JH CONFIRM
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
    delta_offset_v: 0.6   # dICC; omit if datasheet has no dICC
  gaps: []                # honest UNSURE / PROVISIONAL notes
  # AE/FAE handoff (97/126): wire_map from CONFIRMED pins+pin_drive only.
  # settle_prompt (show wait). data_paths folder templates -- never invent nets/cells.
```

Aliases accepted: `logic_dc:` (same mapping as `product_model:`); `vcc_sweep_list`; `threshold_isolation: [{sweep, hold, y_tracks}]`. Shared runner: `ate/tests/logic/logic_dc.py` (import-format alias `ate/tests/logic/dc.py` -- not a second fork).

`pass_mode` on the part yaml (alias `limit_mode`): Schmitt VT+/VT-/hysteresis = `range`; VIH/`VOH` = `min_only`; VIL/VOL/ICC/dICC/II/IOZ = `max_only`.

### What the shared runner derives

- **ICC** -- all `2^n` corners (`logic_inputs`; plus OE when `oe != none`). SIM: 2-input AND = 4, 3-input 97 = 8, 126 A+OE = 4.
- **VIH/VIL (or VT+/VT-)** -- unused ties from the truth table. Prefer a combo where **Y tracks the swept pin non-inverting**. Invert only when no track combo exists (See Lim RS1G97 algorithm; not a per-SKU hardcoded forever). `isolation_for_run` skips rows marked `PROPOSED` / `HOLD CONFIRM`. Per-VCC VIH min / VIL max come from `vcc_grid` (owning fixed point or range band). Range steps inherit band limits -- never a fixed-point row. `vcc_grid.status` UNCONFIRMED is not greenable.
- **II** -- per input, VI=0 and VI=max.
- **Delta ICC** -- one input at VCC-offset.
- **IOZ** -- only when OE/3-state exists. Do not enable `ioz` / `ioff` on parts with `oe: none`.
- **VOH/VOL** -- loaded rows from `voh_table` / `vol_table`. RS1G97/RS1G126 use the CONFIRMED Full IOH/IOL grid (same table). No invented extra loads. Unloaded only when the table is absent.
- **Settle** -- recipe `settle_s=0.05`, `stable_n=3`, `stable_eps_V=0.005`, `settle_timeout_s=2.0`. Voltage (VOH/VOL/threshold) uses `stable_eps_V`. Current (ICC/ΔICC/II/IOZ) uses `stable_eps_A` only. Never reuse `stable_eps_V` as amps (0.005 V is not a 5 mA window). Do not invent a uA default. If `stable_eps_A` is set (panel / overlay), eps/N + hard timeout FAIL (never last-reading). If null: tight-settle claims stay FAIL-closed; honest path waits `settle_s` once then measures and tags `settle=NON_TIGHT` (not greenable as tight-settle). Not a DC limit.
- **AE/FAE Continue** -- every enabled Path B id surfaces `wire_map` (CONFIRMED pins + `pin_drive` only; never invent nets), stimulus, `settle_prompt` (show wait), measure + `pass_mode`, FAIL attach, then `data_paths` save folders. `check_logic_dc` FAIL-closes empty `wire_map` / missing `data_paths` on 97/126.

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

RS1G97 Datasheet §4 table in part yaml is **CONFIRMED** (Jian Hong 2026-09-17; `RS1G97_card_CONFIRMED.md`). Isolation C-track `A:H B:L` is unlocked and used at run; invert `A:L B:H` stays. RS1G126 truth_table / isolation are the same CONFIRMED gate. New SKUs stay UNCONFIRMED until a signed card. Do not invent IOH/IOL. No bench green claim.

### Version overlay

`#Test_Database/.../{Operator}/Version_N/_manifest/test_params.yaml`

```yaml
vcc_list: [3.3]
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
python -m ate.core.check_family_load
python -m ate.core.check_test_detect
python -m ate.core.check_specs_datalog
python -m ate.core.check_ui_contract
```

A green check that never could fail is not a check. Do not claim bench PASS from SIM. `check_logic_dc` fail-closes while a Path B truth_table is UNCONFIRMED; RS1G97 and RS1G126 are CONFIRMED (Jian Hong 2026-09-17) and pass that status gate.

## Do not

- Fork `ate/tests/logic/logic_dc.py` per SKU
- Call `input()` in a `TestSpec.run`
- Import `Lim.*` / `Ariff.*` / `Soo.*`
- Copy See Lim / Ariff trees into limits yaml
- Enable IOZ/IOFF when `oe` is none
- Invent VOH load tables
- Invent a uA `stable_eps_A` default, or reuse `stable_eps_V` as amps
- Touch `family_ingest` / `FAMILY_PACKAGES` for a new RS1Gxx
- Claim Verify PASS / Datasheet-signed from an UNCONFIRMED table
