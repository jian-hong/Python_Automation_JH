# ATE agent + vibe-coder guide (PythonAutomation)

Read this before editing the operator console, adding a person, or adding a product family.

This repo has two stacks. **The live product is the operator console** (`ate/` + worker **8766** + UI **5174**). Root `main.py` / `opa_tests.py` / `logic_tests.py` is the **legacy dual-stack**. Do not start a new test, user, or campaign there. Golden bodies may be copied *from* those files into `ate/tests/<family>/` via Setup Detect/Wrap -- that is ingest, not a second runtime.

Two ways to get the console:

| Who | What they get | Database |
|-----|---------------|----------|
| **App user** | Zip from `pack_ate_console.py`, double-click `START.bat` | Same SharePoint-synced `#Test_Database` (path in `ate/config/cloud_db.txt`) |
| **Vibe-coder** | `git clone -b eugene-console` this repo, read this file | Same folder. Do not invent a private unzip copy |

Paste the SharePoint *https* link into `ate/config/sharepoint.url` when you have it. Each PC still needs the *local OneDrive path* in `cloud_db.txt` (Windows cannot treat the https URL as a folder). A13 Graph stays parked. START/DEMO write `sessions/` + Excel paste into that folder; OneDrive uploads. No second cloud writer.

Daily clone update: `python -m ate.core.sync_repo` (Cursor folder-open + `run_ate_app.bat`). `git pull --ff-only` only when the tree is clean. Dirty tree = fetch only. Never `reset --hard`.

Longer plug-in detail: `docs/ATE_PLUGIN.md`. Logic DC SKUs: `docs/LOGIC_DC.md`. AE/FAE Path B handover: `HANDOVER.md` / `docs/LOGIC_DC_HANDOVER.md`. Operator bench (not a reproduce claim): `docs/LOGIC_DC_OPERATOR.md`. UI chrome: `ate/ui/web/UI_CONTRACT.md`. Human landing: `README.md`.

## Mental model (do not invent a fourth axis)

| Word | What it is | What it is not |
|------|------------|----------------|
| Family | Left rail: `opamp` / `logic` / `switch` / `level` (+ extras) | A person. `lim` is an alias for analog switch |
| Operator | A person folder under the campaign (`Eugene`, `Ariff`, ...) | A family. Top-right **All** is view-only |
| Campaign | One Version tree with workbook + sessions | A website SKU dump |
| Tracking row | `ate/config/inventory.yaml` (what we test now) | RUN-IC homepage catalog |

**Same project, different people** is already the database shape:

```
#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/
```

Example: ChangThong and Ariff both run RS1G08 SC70-5. That is two operator folders under the same part/package, not a fork of the repo and not a Users table.

```
#Test_Database/Logic/RS1G08/SC70-5/Ariff/Version_1
#Test_Database/Logic/RS1G08/SC70-5/ChangThong/Version_1
```

Each person gets their own `_manifest/`, `workbook/`, `sessions/`. Do not overwrite someone else's Version folder. Do not add `Tags` or `Users` as a path segment. Tags live in `_manifest/tags.yaml` + campaign-root `TAGS.txt`.

## Where to change (stop at the first row that holds)

| I want to... | Touch these | Do not touch |
|--------------|-------------|--------------|
| Add a **person** (new operator) | `ate/config/owners.yaml` then Setup owner dropdown (Ctrl+F5). Pick that person (not All). Setup -> New product or Apply campaign so `#Test_Database/.../{TheirLabel}/Version_1` exists | `database.py` path shape; a SQL users table; family rail; `runner.py` |
| Take over a product already in the DB | Same Component/Part/Package. Switch operator to yourself. Type a new Version_N in the Version box then Apply | Copy-replace the other person's `workbook/` or `sessions/` |
| Add a **Version** | Setup Version box (pick or type, same as labels). Apply campaign runs `ensure_version`. Copies `_manifest` stubs from the current version if missing; does not clone xlsx | Excel merge tools; a second campaign root |
| Add a SKU we are testing | One row in `ate/config/inventory.yaml` (part + model + package + lot). RS0204 stays `category: level` + `ate_suite: logic`. Do not scrape en.run-ic.com | `run_ic.yaml` homepage SKUs (RS724-Q1 ...) |
| New part defaults / enabled tests | `ate/config/parts/<key>.yaml` | `runner.py` import lists |
| Logic DC SKU (2/3/N input) | `docs/LOGIC_DC.md` + part `product_model` + `ate/config/limits/<key>.yaml`. Isolation derives from truth_table. Version overlay `_manifest/test_params.yaml` | Fork `logic_dc.py`; per-chip Python; wizard / xyflow |
| New **test** in an existing family | `register(TestSpec)` in `ate/tests/<family>/` + add id to that part's `enabled_tests`. Restart worker | `main.py`, `runner.py`, `input()`, `import Lim.*` / `import Ariff.*` |
| Wrap a golden `test_*` | Setup Detected tests -> Wrap (AST only). Blocked if the golden calls `input()` | Pasting vendor trees into `ate/` |
| Copy tests to another part | Setup Copy tests -- **same family only** | RS0204 dual-rail ids onto RS1G07 |
| New **family** | Setup Import family, or `ate/tests/<family>/` + `ate/config/extra_families.yaml` | Editing `FAMILY_PACKAGES` in `registry.py` (built-ins only). Never ingest into `opamp`/`logic`/`level` |
| RUN-IC class / stub suite | `ate/config/run_ic.yaml` (`live: false` until a suite exists) | Pointing Power/Comparator at OpAmp |
| Photo cell in Excel | Campaign `_manifest/sheet_map.yaml` `tests.<key>.paste.photos` | Hardcoded A91 in Python; a second Excel writer |
| Numeric cell in Excel | Campaign `sheet_map.yaml` `tests.<key>.paste.values` (id -> cell, DUT list, or CHA/CHB grid). Known cells live in `ate/core/campaign_outline.py` (RS622 keys; VOX G16 / ICC D10 / Iplus B2 / GBW R20 or C21). Results -> Fill Excel numbers | Inventing cells; FILL_ME stubs; OpAmp golden on Logic |
| Datasheet min/max | Local `Downloads/Reference/Reference` via `ate/core/lookup.py` + `ate/config/limits/<key>.yaml`. Website only if PDF missing | Catalog scrape into `#Test_Database` |
| Paste / golden layout | `ate/reporting/lab_report.py` + `session_paste.py` / `golden_layout.py` | Unparking A13 OneDrive MCP |
| Operator UI page / tab | `ate/ui/web/index.html` + `app.js` + `styles.css` per `UI_CONTRACT.md`. Bump `?v=` | Second nav, fourth webfont, new CSS framework |
| PSU on | `power_on_protected` only | DP832 30 V / 3 A; unprotected `power_on` |
| Instruments / VISA | `ate/instruments/` + existing `*_setup.py` helpers | Rewriting PyVISA as a new stack |
| Tags / STS datalog | `ate/core/tags.py`, `datalog.py` | Tags folder under `#Test_Database` |
| Living latest JSON / merge | `ate/core/datalog.py` `sync_report_from_session` -- merge by test_id+dut(+channel); keep tests not run this START | Wipe `report.json`; share one latest file across operators |
| Per-test history records | `{test_key}/DUT_n/records/{test_id}_{timestamp}.json` via `write_step_record` | Tags/Users path axis; overwriting history files |
| See who ran what / delete a session JSON | Results -> Run ledger (`list_runs`). Chip `x` or Tags -> Clear all tags | Deleting Version folders; unparking A13 SharePoint MCP |
| Point the lab at a shared cloud folder | `ate/config/sharepoint.url` (https) + each PC `ate/config/cloud_db.txt` (OneDrive path). `bench.yaml` `test_database_root` still works on this bench | A second Excel writer / Graph API / A13 / a private `#Test_Database` inside the app zip |
| Daily git update (clone PCs) | `ate/core/sync_repo.py` -- ff-only, skip if dirty | `git reset --hard`; stash-on-open; merge that can clobber edits |

Worker JSON-RPC surface: `ate/worker/server.py`. Add a method only when Setup/Run already cannot do the job via yaml + existing RPC (`ensure_product`, `ensure_version`, `list_owners`, `import_family`, ...).

## Add a person (copy this)

1. Setup **Operator folder**: type the person's name (folder name on disk). **Save person** or **Apply campaign**. That writes `ate/config/owners.yaml` (`id` lowercase ascii, `label` = folder). Current Component/Part/Package is their default + `task`.
2. Pick that person (not All). **Create folders + open** or Apply so `#Test_Database/.../{TheirLabel}/Version_1` exists.
3. `parts:` is their default picker list, not an ACL. Other people can still open the same part.
4. Do not add `id: all` clones. **All** stays view-only. **Forget person** drops the yaml row only (Version folders stay).
5. Agents may still append yaml by hand; the console path is the operator path.

```yaml
  - id: jane
    label: Jane
    default_family: logic
    default_part: rs1g08
    default_component: Logic
    default_package: SC70-5
    parts: [rs1g08]
    task: RS1G08
```

Then Jane's tree is `Logic/RS1G08/SC70-5/Jane/Version_1`. Ariff's tree next to it is untouched.

`inventory.yaml` `pic:` is the tracking-sheet owner. It does not lock the part. Empty pic must not clobber another SKU of the same part (see `migrate_operator_folders._pic_label_map`).

## Add a test (STANDARD FORMAT -- match Setup)

Three live-UI paths. Detail + Path B yaml: `docs/LOGIC_DC.md`. Plug-in list: `docs/ATE_PLUGIN.md`.

| Path | Live UI | Check |
|------|---------|-------|
| **A -- new body** | `register(TestSpec)` below; checkbox under Setup **Test program** after worker restart | `check_family_load` |
| **B -- Logic DC recipe** | Same DC ids; Setup **Logic DC recipe** + part/limits yaml | `check_logic_dc`, `check_add_test` |
| **C -- Detect / Wrap** | Setup **Detected tests (golden + ate/tests)** -> **Wrap + enable on part** | `check_test_detect` |

`pass_mode` (range / min-only / max-only / fail-open / unspec) is first-class on limits yaml + Test program / Logic DC panel. Missing limits stay unspec unless fail-open (then fail -- never fake PASS).

## Add a test (Path A template)

```python
# ate/tests/<family>/my_slot.py
from ate.core.registry import TestSpec, register

def run(instr, params) -> dict:
    # power_on_protected; params.pause_hook for Continue; never input()
    return {"summary": "...", "data": {}}

register(TestSpec(
    id="my_slot",
    label="My slot",
    required_instruments=frozenset({"PSU", "DMM"}),
    fixture_mode="LOGIC",  # or BUFFER / G11 / LIM_RS2323 -- family-local
    lab_sheet="MySheet",
    run=run,
))
```

Add `my_slot` to `ate/config/parts/<key>.yaml` `enabled_tests`. Return `data` numbers (or `measurements: [{id, value, unit}]`). Limits live in `ate/config/limits/<key>.yaml` (`min`/`max`/`typ` + `pass_mode`: range / min-only / max-only) -- the runner stamps PASS/FAIL into `sessions/report.json` and writes STS `datalog.md|.html|.pdf`. Idle-restart worker. Map `excel_sheet` in that campaign's `sheet_map.yaml` when a workbook sheet exists.

Logic DC (Path B): same shared ids (`input_threshold`, `icc`, ...). Add a SKU with truth table + pin roles + limits only -- see `docs/LOGIC_DC.md`. Do not fork `logic_dc.py`.

Copy-paste prompts: `docs/PROMPT_GUIDE.md`.

## Blast radius (files that break everyone)

| File | If you edit it |
|------|----------------|
| `ate/core/database.py` | Every campaign path on disk |
| `ate/core/runner.py` | Every START / DUT / channel gate |
| `ate/core/registry.py` | Family load for the whole console |
| `ate/worker/server.py` | Every RPC the UI calls |
| `ate/ui/web/*` | Every operator; follow UI_CONTRACT |
| `main.py` / root `*_tests.py` | Legacy only. Console will not see it until wrapped |

Prefer yaml + one `TestSpec` over a clever helper used by all families.

## Ports

- Worker JSON-RPC: **8766** (`ate.worker.server`)
- UI: **5174** (`ate/ui/dev_server.py` via `run_ate_app.bat`)
- Do not use 8765 (AirGPT) or founder-reserved 3000 / 3001 / 5000

## After code the worker loads

Idle-restart with `restart_ate_worker.bat` when you change `ate/core/runner.py`, `ate/worker/**`, `ate/tests/**`, `opa_tests.py`, instrument session helpers. Do not restart mid-run.

Static UI (`ate/ui/web/**`): tell the operator **Ctrl+F5**. Restart the worker if you added/changed an RPC.

`owners.yaml` / `inventory.yaml` / part yaml: RPC re-reads the file. Ctrl+F5 is enough unless the worker is already wedged.

## Checks (run the layer you touched)

```
python -m ate.core.check_new_product
python -m ate.core.check_operator_tree
python -m ate.core.check_ui_contract
python -m ate.core.check_family_load
python -m ate.core.check_open_inventory
python -m ate.core.check_test_detect
python -m ate.core.check_tags_datalog
python -m ate.core.check_lookup
python -m ate.core.check_cloud_db
python -m ate.core.check_sync_repo
python -m ate.core.check_campaign_outline
python -m ate.core.check_session_values
python -m ate.core.check_specs_datalog
python -m ate.core.check_logic_dc
python -m ate.core.check_add_test
```

A green check that never could fail is not a check. Do not claim PASS without running it.

## Do not

- Add a Tags or Users folder axis under `#Test_Database`
- Hardcode A91 photo cells in Python (use sheet_map)
- Invent a second Excel writer / unpark A13 OneDrive MCP / A14 xyflow
- Scrape en.run-ic.com into `#Test_Database`
- Call `input()` in a `TestSpec.run` (blocks the worker; use Continue / `pause_hook`)
- Import vendor packages (`Lim.*`, `Ariff.*`, `Soo.*`)
- Point stub RUN-IC classes (Power, Comparator, ...) at the OpAmp family
- Use operator=All for Create folders / DEMO / START
- Rewrite the left rail, fonts, or tab chrome "to look modern"
- Touch A16 detect/wrap UI when working A17 tags (and the reverse)
