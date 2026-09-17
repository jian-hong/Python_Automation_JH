# Path B Logic DC -- operator

**PR #5 HEAD SHA:** `0095b24`

This file is the bench/operator map. Writer/import format stays in `docs/LOGIC_DC.md`. Verify is a separate agent. This page is **not** a reproduce claim and does **not** claim Verify PASS / bench green.

Settle loop (this PR): recipe `settle_s=0.05`, `stable_n=3`, `stable_eps_V=0.005`, `settle_timeout_s=2.0`. Voltage (VOH/VOL/threshold) waits eps/N vs `stable_eps_V`. Current (ICC / ΔICC / II / IOZ) uses `stable_eps_A` only -- 97/126 default is **null**. Do **not** reuse `stable_eps_V` as amps (0.005 V would be a 5 mA window). Do **not** invent a uA epsilon.

- Tight settle-to-stable (`stable_eps_A` set via panel / `_manifest/test_params.yaml` overlay): eps/N + hard timeout. Timeout raises `RuntimeError` / FAIL. It does **not** return the last reading.
- Null `stable_eps_A`: tight-settle **claims** stay FAIL-closed. Honest path waits `settle_s` once then measures and tags `settle=NON_TIGHT` (not greenable as tight-settle).
- Ground `stable_eps_A` (amps) on the Logic DC panel overlay before claiming current settle-to-stable.

`check_logic_dc` also FAIL-closes **enabled-but-unrunnable** ids: every part `enabled_tests` id must have a registered `TestSpec` with callable `run` (no stub).

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

Use these without a live DMM/PSU/AWG. They prove schema and UI, **not** instrument physics.

1. Product-model schema load (`ate/config/parts/<key>.yaml` `product_model` / `logic_dc:`). Isolation derives from `truth_table` (Y tracks the swept pin; invert only if no track combo).
2. `pass_mode` on part yaml + limits yaml + Setup **Logic DC recipe** / Test program (range / min_only / max_only / fail-open / unspec). Missing min/max stay **unspec** unless fail-open.
3. Fail-closed until Datasheet-signed **CONFIRMED**. UNCONFIRMED SKUs cannot green. RS1G97 and RS1G126 are CONFIRMED (Jian Hong 2026-09-17) for the status gate only -- that is not a bench green.
4. Panel recipe edit: JSON **Save product_model** writes part yaml from `docs/datasheet/card_fields.schema.yaml` (cannot promote to Datasheet-signed). Visual tables **Save Version overlay** write `#Test_Database/.../{Operator}/Version_N/_manifest/test_params.yaml` (vcc_list, pass_mode, `stable_eps_A`).
5. `python -m ate.core.check_logic_dc` (also `check_add_test`, `check_family_load`). Visa-free SIM: rs1g08 ICC corners=4, rs1g97=8, rs1g126 A+OE=4. Timeout SIM raises. **Not a reproduce claim.**

DEMO on Run walks ticked tests with mock numbers and writes `sessions/` JSON. It does **not** stamp the lab xlsx as PASS. DEMO is not PSU->settle->measure.

## HUMAN + real instruments -- required to reproduce

Reproduce Path B DC only with a human, Open Session, and live PSU + DMM + AWG wired to the DUT. Continue prompts (ICC / II / IOZ) are recable steps -- follow them. Fixture text is `fixture_modes.LOGIC.checklist` on the part yaml (Setup/Run checklist), not a second wiring table.

After each PSU VCC switch and pin force: **PSU -> settle -> measure**. Voltage must hold `stable_n` inside `stable_eps_V`. Current: if `stable_eps_A` is set, hold `stable_n` inside **`stable_eps_A`** (amps) or **FAIL** on timeout. If `stable_eps_A` is null/missing, the runner does **not** reuse `stable_eps_V`; it waits `settle_s` once, measures, and tags `settle=NON_TIGHT` (not greenable as tight-settle). Tight-settle **claims** without `stable_eps_A` stay FAIL-closed. If the DMM never settles before `settle_timeout_s` on the tight path, the step **FAIL**s. Do not treat a timed-out last reading as PASS.

| Id | Sense (from `logic_dc.py` INSTRUMENT_SENSE) | Notes |
|----|-----------------------------------------------|-------|
| ICC | DMM-on-VCC (DMM in series with PSU CH1 / DUT VCC) | All `2^n` corners. Null `stable_eps_A` = NON_TIGHT. Overlay amps for tight settle-to-stable |
| ΔICC | DMM-on-VCC; one input at VCC-offset, others at rail | Needs `recipe.delta_offset_v` (97/126: 0.6). Do not invent the offset |
| II | DMM in series with the swept input; force VI | Per input, VI=0 and VI=max |
| VTH / VIH / VIL | Force unused ties from truth_table; DMM sense V(Y) | 97 Schmitt = VT+/VT- (range). 126 = VIH min_only / VIL max_only |
| VOH | Force Y=H from truth_table; DMM sense V(Y); IOH via PSU CH2 | Loaded rows only from CONFIRMED `voh_table`. Judge **VOH >= min** (`min_only`) |
| VOL | Force Y=L from truth_table; DMM sense V(Y); IOL via PSU CH2 | Loaded rows only from CONFIRMED `vol_table`. Judge **VOL <= max** (`max_only`) |
| IOZ | Only if OE exists. OE inactive; DMM in series with Y; PSU CH2 force Vout | 126: yes. 97 `oe: none`: do **not** tick ioz |

PSU CH1 is VCC. PSU CH2 is Y-load/vref (VOH sink rail 0V, VOL source rail = VCC -- fixture, not a datasheet Vref). RS1G97 pin C is PSU CH3 (checklist: AWG CH1=A CH2=B). RS1G126: AWG CH1=A CH2=OE; no C.

Do not invent extra IOH/IOL rows. Tables live in part yaml + `ate/config/limits/`.

## Excel path -- never invent cells

Campaign tree:

```
#Test_Database/{Component}/{Part}/{Package}/{Operator}/{Version_N}/
  workbook/                 # lab xlsx (Import xlsx / Create folders)
  _manifest/sheet_map.yaml  # folder <-> sheet <-> paste anchors
  _manifest/test_params.yaml
  sessions/
  {TestKey}/DUT_n/
```

**Results -> Fill Excel numbers** writes `sheet_map` `tests.<key>.paste.values` from living `sessions/report.json`. Photos use `paste.photos`. Do **not** invent Excel cells in this doc, in Python, or in chat.

Paste cells come from, in this order only:

1. That campaign's `_manifest/sheet_map.yaml` (operator-filled from the **live** workbook).
2. Known keys already in `ate/core/campaign_outline.py` **when those sheets exist on the imported xlsx** -- do not add corners that are not on the sheet:
   - Logic VOX sheet: `VOH_4p5V` DUT list `G16` / `H16` / `I16`; `VOL_4p5V` `G25` / `H25` / `I25`
   - Logic ICC sheet (not RS0204 `Icc` grid): `ICC_uA` `D10`
3. Import may stub `FILL_ME`. A human fills real cells from the tracking xlsx. A filled map is not overwritten without a `.bak_*` backup.

The CONFIRMED 97/126 VOH/VOL Full grid (100uA + 4/8/16/24/32mA ids in part yaml) is **limits + runner**, not a license to mint new paste cells here. If the workbook has no cell for an id, Fill Excel skips it. Map coverage is Setup **Map coverage**.

## Log path

| What | Where |
|------|--------|
| Living latest merge | `{Version_N}/sessions/report.json` |
| Full START snapshot | `sessions/session_*.json` |
| STS datalog | Results **Export STS datalog** -> `sessions/datalog.md` + `.html` + `.pdf` |
| Per-step history | `{test_key}/DUT_n/records/{test_id}_{timestamp}.json` (append-only; never overwrite) |

Never dump the RUN-IC catalog into `#Test_Database`. Delete on Results **Run ledger** removes a session JSON only -- never the Version folder or workbook xlsx.

## Console

Zip operators: `START.bat` (from `ATE_Console_Try_*.zip`). Clone PCs: `run_ate_app.bat`.

- UI: `http://127.0.0.1:5174`
- Worker JSON-RPC: `http://127.0.0.1:8766` (not 8765)
- After `git pull` / zip refresh: **Ctrl+F5**
- After `ate/tests/**` / worker changes: idle-restart worker (`restart_ate_worker.bat`), not mid-run, then Ctrl+F5

Pick a **person** (not All) -> Apply campaign -> Discover -> Open Session -> tick tests -> START.

## Human-test checklist -- RS1G97 + RS1G126 (Path B)

Short. Same Path B runner. Tick only DC ids below (97 has no IOZ; 126 keeps ten/tdis as AC -- do not treat them as this DC list).

**Both parts**

1. Console up (5174 / 8766). Person selected. Campaign `#Test_Database/Logic/RS1G97/...` or `.../RS1G126/...` applied.
2. Discover. **Open Session** (PSU + DMM + AWG present; DMM required at run for these ids).
3. Run fixture checklist (part yaml `fixture_modes.LOGIC.checklist`). Wire DMM+PSU+AWG to that text. Continue when the runner asks to recable (ICC series-VCC vs II series-input vs IOZ series-Y vs VOH/VOL DMM-on-Y).
4. Tick Path B DC: `input_threshold` (and/or `vth`), `icc`, `delta_icc`, `ii`, `voh`, `vol`. 126 also tick `ioz`. 97 must **not** tick `ioz` / `ioff`.
5. START (not DEMO). Confirm an unstable DMM **settle timeout hard-FAIL**s (RuntimeError / FAIL) when `stable_eps_A` is grounded, not a last-reading PASS. Recipe timeout 2.0 s. Null `stable_eps_A` is NON_TIGHT (wait `settle_s` once); do not invent uA. Tight-settle claims stay FAIL-closed until overlay/panel sets `stable_eps_A`.
6. On a stable bench: Results / `report.json` -- **VOH >= min** vs CONFIRMED `voh_table` / limits (`min_only`); **VOL <= max** vs CONFIRMED `vol_table` (`max_only`). Do not invent extra loads.
7. Fill Excel only via sheet_map / campaign_outline (above). Export STS if needed. No Verify PASS claim from this checklist.

**RS1G97 extra**

- Schmitt: VT+ / VT- / HYST = range. C on PSU CH3. `oe: none`.
- ICC corners = 8 (A,B,C).

**RS1G126 extra**

- VIH min_only / VIL max_only. OE active high. IOZ when OE inactive (data don't-care; Vout sweep per recipe `ioz_vcc_list` / `ioz_vout_list` already on the card -- do not invent).
- ICC corners = 4 (A+OE).
