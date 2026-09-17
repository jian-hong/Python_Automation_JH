# STANDARD FORMAT -- write / import a test (live UI)

Live console only (`ate/` + worker **8766** + UI **5174**). Vibe-coder map: `AGENTS.md`. Plug-in slots: `docs/ATE_PLUGIN.md`. UI chrome: `ate/ui/web/UI_CONTRACT.md`. Path B TestSpecs stay physics bodies. Do not add wizard-Python, xyflow, a second runner, or scrape en.run-ic.com.

New RS1Gxx (2-input, 3-input, N-input, with/without OE) should not need a forked `logic_dc.py`.

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
    delta_offset_v: 0.6   # dICC; omit if datasheet has no dICC
  gaps: []                # honest UNSURE / PROVISIONAL notes
```

Aliases accepted: `vcc_sweep_list`; `threshold_isolation: [{sweep, hold, y_tracks}]`.

`pass_mode` on the part yaml (alias `limit_mode`): Schmitt VT+/VT- = `range`; VIH/`VOH` = `min_only`; VIL/VOL/ICC/dICC/II/IOZ = `max_only`.

### What the shared runner derives

- **ICC** -- all `2^n` corners (`logic_inputs`; plus OE when `oe != none`). SIM: 2-input AND = 4, 3-input 97 = 8, 126 A+OE = 4.
- **VIH/VIL (or VT+/VT-)** -- unused ties from the truth table. Prefer a combo where **Y tracks the swept pin non-inverting**. Invert only when no track combo exists (See Lim RS1G97 algorithm; not a per-SKU hardcoded forever). `isolation_for_run` skips rows marked `PROPOSED` / `HOLD CONFIRM`.
- **II** -- per input, VI=0 and VI=max.
- **Delta ICC** -- one input at VCC-offset.
- **IOZ** -- only when OE/3-state exists. Do not enable `ioz` / `ioff` on parts with `oe: none`.
- **VOH/VOL** -- when catalog-enabled. Loaded rows only from existing `voh_table` / `vol_table`. No invented loads (PROVISIONAL unloaded otherwise).

RS1G97 Datasheet §4 table in part yaml is **UNCONFIRMED** (not Datasheet-signed, not greenable). Isolation C invert `A:L B:H` is the See Lim fallback used at run. C-track `A:H B:L` is stored as **PROPOSED HOLD CONFIRM** and skipped until a signed confirm. RS1G126 truth_table is the same fail-close (UNCONFIRMED; not `from_datasheet_function_table`). Do not invent IOH/IOL.

### Version overlay

`#Test_Database/.../{Operator}/Version_N/_manifest/test_params.yaml`

```yaml
vcc_list: [3.3]
levels: {}      # optional recipe
rails: {}       # optional recipe
pass_mode:
  ICC_uA: max-only
  VTPLUS_V: range
  VOH_5p0V: min-only
```

Setup **Logic DC** panel:

- JSON editors + **Save product_model** write part yaml (`save_product_model`). Cannot promote status to Datasheet-signed.
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

A green check that never could fail is not a check. Do not claim bench PASS from SIM. `check_logic_dc` stays FAIL-CLOSED while RS1G97 truth_table is UNCONFIRMED.

## Do not

- Fork `ate/tests/logic/logic_dc.py` per SKU
- Call `input()` in a `TestSpec.run`
- Import `Lim.*` / `Ariff.*` / `Soo.*`
- Copy See Lim / Ariff trees into limits yaml
- Enable IOZ/IOFF when `oe` is none
- Invent VOH load tables
- Touch `family_ingest` / `FAMILY_PACKAGES` for a new RS1Gxx
- Claim Verify PASS / Datasheet-signed from an UNCONFIRMED table
