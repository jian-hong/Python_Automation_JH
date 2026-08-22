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
3. **`FAMILY_PACKAGES` line** — `ate/core/registry.py` must map
   `"<family>": "ate.tests.<family>"`. Worker `set_family` / UI rail read this.
4. **Optional part yaml** — `ate/config/parts/<key>.yaml` (fixture modes, gain
   boards, sample_size). Only if the part needs bench defaults.
5. **Worker restart** — `restart_ate_app.bat` (ports **8766** worker, **5174**
   UI). **8765 is AirGPT — leave it alone.** Registry loads at worker start.

## Campaign slots (`#Test_Database`)

Tree: `{Component}/{Part}/{Package}/{Version_N}/`

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

## After plug-in

- Apply campaign in Setup → Discover → Open Session → select tests → START.
- Confirm family rail shows the new family and `list_tests` returns the specs.
