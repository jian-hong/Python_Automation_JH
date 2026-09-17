# ATE plug-in checklist (one-prompt scale)

Companion to `ATE_MODULAR.md`. Fill **every** slot below when adding a family
or a new campaign. Do not invent instruments. Do not clone GitHub into the
test tree (`Github_Auto/` is a team git helper, not ingest).

## Code slots

1. **Family package** — `ate/tests/<family>/` with `__init__.py` that imports
   modules which call `register(TestSpec(...))`.
   - OpAmp example: `ate/tests/opa/` (`vos`, `ac_*`, `slew`, `gbw`, `ort`, …).
   - Logic / Level already have package keys; Level is still a stub suite.
2. **`register(TestSpec)`** — each test: `id`, `label`, `required_instruments`,
   `fixture_mode`, `lab_sheet`, `run` callable. Optional: `notes`, `fixed_steps`,
   `dual_channel`, `short_tag`.
3. **Family map** — built-ins stay in `FAMILY_PACKAGES` (`ate/core/registry.py`):
   opamp → `ate.tests.opa`, logic, level. **New families do not need a hand
   edit.** Prefer `ate/config/extra_families.yaml` (`families.<key>.package`)
   and/or a package under `ate/tests/<family>/` (pkgutil discovery). Worker
   `set_family` / UI rail read `known_families()`.
4. **Optional part yaml** — `ate/config/parts/<key>.yaml` (fixture modes, gain
   boards, sample_size). Only if the part needs bench defaults.
5. **Worker restart** — ingest calls `refresh_family_table()` in-process. If
   the family rail is stale, `restart_ate_app.bat` (ports **8766** worker,
   **5174** UI). **8765 is AirGPT — leave it alone.**
6. **Instruments** — Discover classifies MSO / PSU / AWG / **DMM** (`ate/instruments/discovery.py`).
   DMM is optional at Open Session. Tests that need it (Logic IDD/VOUT/cap_load, OpAmp VOL)
   fail at run if it is missing. Header tile **DMM** turns on when found.

## GitHub / local family ingest

Setup → **Import family** (RPC `import_family`). This is the next-time drop-in
path. It is **not** a clone of this repo and it does **not** `git init` under
`ate/`.

1. Paste a GitHub URL (`https://github.com/org/repo`, `org/repo`, or
   `.../tree/<branch>/path/to/family`) **or** a local family folder / `.py`.
2. Optional family key (example `analog`). Do **not** use `opamp` / `opa` /
   `logic` / `level` — those packages are protected. Do not ingest into opamp.
3. Worker downloads a zipball (or copies the local folder) into a temp dir,
   then copies **only** `*.py` test modules into `ate/tests/<family>/`.
4. Fail-closed: the source must look like an ATE family (`register(TestSpec)`
   or a thin adapter that still calls `register`). A random repo, or this
   full ATE tree (`ate/core` + `ate/tests/opa`), is rejected with the slot
   list above.
5. Existing `opamp`/`logic`/`level` modules are never the dest. Replacing a
   previous extra family backs it up under `ate/tests/_backup/`.
6. `ate/config/extra_families.yaml` is updated. No secrets. Then the worker
   reloads the family table; extra keys appear on the Family rail.
7. Then: Apply campaign → Discover → Open Session → select tests → START.
   Workbook paste cells still come from `import_workbook` + `sheet_map`, not
   from this ingest.

## Campaign slots (`#Test_Database`)

Tree: `{Component}/{Part}/{Package}/{Operator}/{Version_N}/`

Operator is a person folder (Eugene / Ariff / …). Top-right **All** is view-only -- Create folders / DEMO / START require a real person. Migrate legacy trees with `python -m ate.core.migrate_operator_folders --apply`.

6. **Campaign folders** — `_manifest/`, `workbook/`, `sessions/`, plus per-test
   `{TestKey}/DUT_N/{screenshots,graphs}`.
7. **Workbook xlsx** — live lab report under `workbook/`. Import an existing
   file from Setup (RPC `import_workbook`); do **not** use an upload wizard.
8. **`_manifest/sheet_map.yaml`** — folder ↔ Excel sheet ↔ paste anchors.
   Import may **stub** this from sheet names (`FILL_ME` paste cells). An
   operator must fill real cells. A map that already has anchors is not
   overwritten without a `.bak_*` backup.
9. **`_manifest/test_catalog.yaml`** — operator conditions / recipes (not
   invented by import).

Excel writes go through `ate/reporting/lab_report.py` + `sheet_map` only.

## PSU safety (A15)

Always use `power_on_protected`. Defaults OVP=Vset+0.3 V, OCP=Iset+0.1 A; PROT:STAT ON with readback. Never DP832 30 V / 3 A. Unprotected `power_on` raises.

## Photo / waveform layout (A07)

**Where to change image boxes:** campaign `_manifest/sheet_map.yaml` → `tests.<TestKey>.paste.photos`
(example `u1_chA: A91`, ORT `pos_u1_chA: A46`). Python paste reads
`ate/reporting/photo_layout.py` only -- do not add another A91 dict in `lab_report.py`.

Preview + compare + save: operator console **Results → Waveform layout** (`http://127.0.0.1:5174`).
Save patches the same YAML. Graphs/screenshots stay under `{TestKey}/DUT_N/{graphs,screenshots}`.

## Mapped tests + DMM (A08)

Every `_manifest/sheet_map.yaml` `tests.<key>.excel_sheet` must have a `TestSpec.lab_sheet`.
Setup shows **Map coverage OK**. Remaining OpAmp sheets (PowerOn / EMIRR / PSRR / CMRR / AOL / VOL / Noise)
run as capture + optional DMM read in `ate/tests/opa/mapped_dc.py` -- not RuntimeError stubs.
Check: `python -m ate.core.check_mapped_tests`.

## Family conditions + timing (A04)

Each family owns its Run param catalog and measurement timing defaults.
`ate/core/param_defaults.py` exposes `catalog_for_ui(part, family=...)` and
`timing_for(family, test_id=...)`. OpAmp keeps G11 gain profiles, GBW steps,
and OPA `TEST_DEFAULTS`. Logic gets Logic-relevant fields (e.g. `vcc`) with
no G11 / `cfg_g11` chrome. Other families (`demo_ingest`, ingested extras)
get a family-local catalog only -- do **not** copy OPA settle/timeout literals
(`1.5` / `1.8` / `6.0` s) as the platform default for non-opamp families.
Worker `list_param_defaults` and the UI reload the catalog on family switch.

## Logic campaigns (A09)

Ariff / Soo / Lim are **owner recipe trees** in LabAutomation-1, not three consoles.
One Logic family rail; differences live in YAML:

1. Campaign: `#Test_Database/Logic/<Part>/<Package>/Version_N/` with
   `_manifest/sheet_map.yaml` + `test_catalog.yaml` (+ workbook via Import xlsx).
2. Part yaml: `ate/config/parts/rs29511.yaml` (Soo) and `rs1g08.yaml` (Ariff) --
   fixture `LOGIC`, `vcc`, `current_limit`, timing (`htol_ns`), `enabled_tests`.
3. Run list filters by `enabled_tests` / catalog so RS29511 does not show
   RS1G08-only DC rows. Extra Ariff specs live in `ate/tests/logic/ariff_dc.py`
   (no `import Ariff.*`).
4. Map coverage / lab-report sync follow the **active** campaign family
   (Logic vs OpAmp). Check: `python -m ate.core.check_logic_campaign`.
5. RS1G07 / RS1G14 use the same Logic family + Ariff DC ids via part YAML (A10).
6. RS0204 dual-rail: `ate/config/parts/rs0204.yaml` (vcca/vccb) + campaign `Logic/RS0204/TSSOP14`. Bodies in `ate/tests/logic/rs0204.py` (PSU CH1=VCCA, CH2=VCCB). Do not import `Soo.logic_tests`. Downloads `logic_tests.py` is RS29511/Soo. Check: `python -m ate.core.check_logic_campaign`.
7. Campaign Component folder switches Family (OpAmp/Logic/AnalogSwitch/Level). `set_db_context` calls `family_for_component`.
8. A12 Ariff latest: thickened DC + `supply_current_sweep` / `vih_vil` / `voh_load` / `vol_load`
   (ids distinct from RS0204 `voh`/`vol`). Tables in part YAML. Operator deselects via checkboxes.
   LDO not on RS1G. Reference: Ariff Repo `LabAutomation_v1 - Copy` (do not import).
9. Shared Logic DC (RS1G97 / RS1G126, then other 1G parts): `logic_inputs`, `oe`,
   `logic_dc.truth_table`, `logic_dc.threshold_isolation`, `vcc_sweep_list` in
   `ate/config/parts/<key>.yaml`. One procedure in `ate/tests/logic/dc.py` (ICC 2^n,
   Schmitt isolation, dICC, leakage, IOZ when OE exists). Do not tick Ariff `vih_vil`
   next to `input_thresholds` on RS1G97. Do not copy RS1G08 `voh_table` onto parts
   without a load map. `setup_dc` lives in `generator_setup.py`. Check:
   `python -m ate.core.check_logic_dc` (SIM, no VISA). DEMO does not execute TestSpec.run.

## Analog Switch (was mislabeled Lim)

1. Builtin family key `switch` -> `ate/tests/lim/` (package name historical). Alias `lim` still loads it.
2. Part `ate/config/parts/rs2323.yaml` + campaign `#Test_Database/AnalogSwitch/RS2323/...`.
3. Operator (person) is the top-right selector, not a family. Lim also owns Logic RS1G126/RS1G97.
4. Tests: iplus, leakage_off, leakage_on, input_leakage -- PSU+DMM; wiring via
   operator Continue (`pause_hook`), **never** `input()` and **never** `import Lim.*`.
5. Fixture mode `LIM_RS2323`. Check: `python -m ate.core.check_open_inventory`.
6. LA-1 `Lim/threshold_tests.py` is RS1G126 -- Logic, not Analog Switch.

## How to extend (names, tests, corners)

Do **not** edit `runner.py` to add a product. Full no-code wizard stays parked.
**F23 / A16** adds Setup detect/wrap/copy/+Version/+Session (not a code editor).

1. **New person / operator** -- add a row in `ate/config/owners.yaml` (`id`, `label`, `default_family`, `default_part`, `default_component`, `default_package`, `parts`). Reloads on Setup; top-right Operator dropdown.
2. **New part in an existing family** -- `ate/config/parts/<key>.yaml` (`enabled_tests`, `vcc`, optional `vcc_sweep_list` or `vcc_sweep`, optional `vccb`, `fixture_modes`, `timing`). Create campaign folders under `#Test_Database/{Component}/{Part}/{Package}/{Operator}/Version_N/`. Or Setup **+ Version** for the next `Version_N`.
3. **New test in an existing family** -- preferred engineer path: `register(TestSpec(...))` in that family's package + add the id to the part's `enabled_tests`. Restart/reload worker. Run page shows a checkbox.
4. **Detect / wrap from golden** -- Setup **Detected tests**: AST-scans `ate/tests` + paths in `ate/config/golden_roots.yaml` (missing dirs skipped). Tick wrap-ready rows -> **Wrap + enable on part** writes `ate/tests/<family>/imported_<id>.py`. Rows that call `input()` stay **blocked**. Check: `python -m ate.core.check_test_detect`.
5. **Copy tests between parts** -- same family only: Setup **Copy tests from part** -> **Copy to current part** appends `enabled_tests` (refuses cross-family, e.g. RS0204 dual-rail onto RS1G07).
6. **+ Session** -- writes a new `sessions/session_*.json` run record without START / VISA. Discover -> Open Session still required for instruments.
7. **Dropdown corners** -- if the yaml has `vcc_sweep_list` / `vcc_sweep` (or `controls:` list with `id` / `choices`), Setup shows a **Run conditions** select. Dual-rail parts also get VCCB. OpAmp keeps locked gain boards; Logic/Analog SW do not show G11.
8. **New family** -- Setup -> Import family, or drop `ate/tests/<family>/` + `extra_families.yaml` with optional `label:` for the rail name. Worker `set_family` / left rail pick it up after refresh.
9. **Campaign tree** -- `{Component}` folder switches family. Names with underscores (`demo_ingest`) match the family key.
10. **Tags + session datalog (A17)** -- Tags page / chips write `_manifest/tags.yaml` + `TAGS.txt` (grep). Boards: `ate/config/boards.yaml`. Rolling STS JSON: `sessions/report.json` + `archive/`. Session-end paste via `paste.photos`. See `AGENTS.md`. Checks: `python -m ate.core.check_tags_datalog`, `check_ui_contract`, `ate.reporting.check_golden_workbook`.

Authoring contract for new bodies:

```python
def run(instr, params: RunParams) -> dict:
    # power_on_protected; params.pause_hook for Continue; never input()
    return {"summary": "...", "data": {}}
```

Raw `def test_foo(instr, ...):` is golden-source only until wrapped into `TestSpec`.

## New product + DEMO (tracking sheet, not website catalog)

1. Setup **New product under test**: pick RUN-IC class (`ate/config/run_ic.yaml`) or a tracking-sheet row (`ate/config/inventory.yaml`), enter part/package, **Create folders + open**.
2. Creates `#Test_Database/{Component}/{Part}/{Package}/{Operator}/Version_1/` with `_manifest/`, `workbook/`, `sessions/`, `Setup/DUT_N/{screenshots,graphs}`. Stub part yaml only if missing.
3. Do **not** add RUN-IC homepage SKUs (RS724-Q1 / RS722P-Q1 / ...) until that part is actually under test.
4. **DEMO dry-run** walks selected tests with mock MSO/PSU/AWG/DMM numbers. Writes `sessions/session_*.json` and `DUT_1/graphs/demo_sample.json`. Does not stamp the lab xlsx PASS.
5. Advanced bench (freq / amp / repeats) sits under DUT/Channel. Photo cells stay Results -> Waveform layout.

Then: Apply campaign -> Discover -> Open Session -> select tests -> START.

## After plug-in

- Apply campaign in Setup → Discover → Open Session → select tests → START.
- Confirm family rail shows the new family and `list_tests` returns the specs.
