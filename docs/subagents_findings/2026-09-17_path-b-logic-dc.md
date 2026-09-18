# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g07, rs1g126, rs1gt34, ioz, schmitt, UNCONFIRMED, CONFIRMED, pass_mode, test_params, logic_inputs, eugene-console, seelim, recipe.search, threshold_search, icct, one_input_V, pretty, never_auto_write, csv, path_b_write

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run. Isolation is derived from truth_table (Y tracks swept pin; invert only if no track combo -- See Lim algorithm, not per-SKU hardcodes). ICC corners = 2^n. Version overlay `_manifest/test_params.yaml`. pass_mode first-class (range / min-only / max-only / fail-open / unspec). RS1G97 / RS1G126 truth_table + isolation are CONFIRMED (Jian Hong 2026-09-17). RS1GT34 is CONFIRMED (Jian Hong 2026-09-18): n=1 Y=A, PSU_MSO, no ioz, delta_icc from ICCT 500uA @5.5 one_in@3.4 (not 0.6), recipe.search via threshold_search.py (limit-scaled first step, on-hit skip, no reverse). C-track A:H B:L is unlocked at run. STANDARD FORMAT checklist is `#add-test-format` on Setup Test program (Path A/B/C). `#panel-logic-dc` visualises Customise Parameters (`vcc_grid` FIXED POINTS + RANGE SWEEPS, merged vcc_list preview, PSU_MSO vs AWG), enabled tests, recipe, card_fields (OOP assign/edit/delete including wire_map / settle_prompt / data_paths / vcc_grid / excel_plots / workbook_policy / recipe.search), truth table, isolation, ICC corners, limits+pass_mode. Dual Excel: auto/golden_auto = chosen Version workbook/ overwrite-in-place (`workbook_policy.auto` / `golden_auto: one_per_version_overwrite`); pretty/ultimate_manual = jot (`never_auto_write`, pretty never auto). Continue/Open Session bind fill/plot to golden_auto only. Add SKU: `docs/LOGIC_DC.md`. Operator bench: `docs/LOGIC_DC_OPERATOR.md` (DEMO/SIM is not a reproduce; Path B Excel from excel_plots; imported VOX still sheet_map / campaign_outline). See Lim wrap is `seelim_dc.py` locator only. OOP schema: `docs/datasheet/card_fields.schema.yaml`. Runnable lock: every enabled_tests id must have TestSpec.run callable. AE/FAE Continue: wire_map from CONFIRMED pins+pin_drive only (never invent nets); settle_prompt show wait; data_paths folder templates; FAIL attach `{test}/DUT_n/`.

## traps

- Logic registry is one id namespace: do not register a second `voh`/`vol`/`icc`. Dispatch on product_model vs vcca/vccb.
- Do not invent truth rows or VOH/VOL IOH/IOL numbers. 97/126 tables are CONFIRMED (Jian Hong 2026-09-17). VOH/VOL Full load grid is wired (same table); no extra VCC/load rows.
- check_logic_dc fail-closes UNCONFIRMED SKUs. 97 and 126 pass the Datasheet-signed CONFIRMED status gate. Do not claim bench green.
- 126 unused data ties N/A (single data pin). Only OE-active isolation for A.
- Do not scrape Ariff/See Lim/Eugene trees into YAML. Limits stay in `ate/config/limits/` citing the Reference PDF extract.
- ten/tdis stay AC on 126.
- PSU CH2 is Y-load/vref; RS1G97 pin C is PSU CH3 (PROVISIONAL fixture map).
- Single-rail parts must not inherit RS0204 `vccb` from LOGIC_TEST_DEFAULTS.
- vcc_op_min/max are range metadata, not a sweep. 97/126 vcc_list is the CONFIRMED card grid [1.65, 2.3, 3.0, 4.5, 5.5].
- Do not touch family_ingest / extra_families / registry FAMILY_PACKAGES.
- IOZ/IOFF only when oe != none.
- `#add-test-format` must stay on Test program (always visible), not inside hidden `#panel-logic-dc`.
- settle timeout must raise RuntimeError / FAIL. Never return last reading (measure-as-pass). Never hang forever (no unbounded while True).
- ICC / ΔICC / II / IOZ must settle-to-stable after VCC and each force, not sleep(_settle) then _avg_current_ua.
- Never reuse stable_eps_V as amps. Current settle uses stable_eps_A only. 97/126 default null = NON_TIGHT (wait settle_s once; not greenable as tight-settle). Tight claims without stable_eps_A stay FAIL-closed. Do not invent a uA epsilon. Overlay/panel grounds eps/N.
- enabled_tests must map to a registered TestSpec with callable run (check_logic_dc runnable gate). No stub.
- Panel save keys come from docs/datasheet/card_fields.schema.yaml. PaddleOCR path; do not install Baidu unless asked. See Lim/Ariff are read-only refs.
- Operator Excel: Path B one_per_version_overwrite (one xlsx per Version; never orphan/_filled.xlsx). Headers from runner keys; regex only detects series. excel_plots allowlist. OpAmp/imported VOX still sheet_map / campaign_outline G16/D10 when those sheets exist -- Path B does not mint those cells.
- AE/FAE wire_map only from CONFIRMED pins + pin_drive. PSU CH2 is pin Y use=load (existing VOH/VOL fixture), not a new net. SCOPE CH1 is output_pin Y (debug capture), not IN+/VOUT. check_logic_dc FAIL-closes empty wire_map / missing data_paths on 97/126 only (not rs1g08).
- AE/FAE wire_map only from CONFIRMED pins + pin_drive. PSU CH2 is pin Y use=load (existing VOH/VOL fixture), not a new net. SCOPE CH1 is output_pin Y (debug capture), not IN+/VOUT. check_logic_dc FAIL-closes empty wire_map / missing data_paths on 97/126 only (not rs1g08).
- runner pause_hook must accept checklist= so Logic Continue is not OpAmp IN+/VOUT. Do not wrap TestSpec.run at _register (th.run is ldc._run_input_threshold).
- vcc_grid: range steps inherit band VIH/VIL; fixed_points overwrite exact VCC; 4.5 on 34 is a range step not a third fixed row. Customise Parameters writes overlay `_manifest/test_params.yaml` only. PSU_MSO hides Freq/Amp and keeps YAML pin_drive (do not steal AWG CH1).
- RS1GT34 CONFIRMED (Jian Hong 2026-09-18). Call `_fail_closed_until_signed` (now CONFIRMED). Copy VOH/VOL/II/ICC/ICCT from RS1GT34_card_CONFIRMED only. Expand 100uA onto merged vcc_list; high-load only at card-named VCC. PSU CH2 is pin Y use=load (not a new net). Enable delta_icc from ICCT 500uA @5.5 one_in@3.4 -- do not invent delta_offset_v=0.6. No IOZ (oe none; Ioff is VCC=0). recipe.search via threshold_search.py: limit-scaled first step, on-hit skip, no reverse. Dual Excel: auto overwrite Version; pretty never auto. check_logic_dc FAIL if voh/vol enabled with no table rows. SIM FAIL bars: reverse search, first step > |limit|, auto dest == pretty, invent 0.6, ioz on oe=none, unsigned greenable=False greens PASS.
- Overnight Path B DRAFT scaffold (UNCONFIRMED, no number unlock): inline product_model on rs1g08/rs1g07/rs1g14/rs1g32/rs1gt08/rs1gt32/rs1g125/rs164. Do not call `_fail_closed_until_signed` on these 8 (that would FAIL the suite). Physics FAIL bars in check_logic_dc: G08 AND other=H no IOZ keep AWG; G07 open_drain skip VOH Y=Z not IOZ; G14 Schmitt VT+/- range; G32 OR other=L; GT08/GT32 TTL 2.0-5.5 ICCT 3.4 not 0.6; G125 OE active-L ioz ON (OE inactive H only); RS164 sequential_shift_register not gate 2^n (icc_pins [] / sim n=0). recipe.search on gate SKUs only. Overlay vcc_list must pop vcc_grid. is_open_drain / is_sequential generic (no part-name ifs in logic_dc.py / product_model.py; banned rs1g08/rs1g125 compares). Generic SIM: open_drain+voh enabled FAIL; sequential+icc 2^n FAIL; schmitt collapsing to single VIH FAIL. Do not enable voh/vol without table rows. 08 omit excel_plots. Keep HEAD 85fa7fb GT34 CONFIRMED + threshold_search.
- JH room CONFIRM 2026-09-17: 8 SKUs status+truth_table+isolation CONFIRMED (RS164 isolation N_A). Glyph-missing uA/mA omitted. G07 VOL 4 extract IOL rows CONFIRMED; VOH N/A. Call `_fail_closed_until_signed` now that status+tt+iso are signed. Do not inherit product_model.status onto vcc_grid (own status gate). vcc_plan is Version overlay alias of vcc_grid. Customise Parameters: pin/wiring labels, 2Gxx dual-channel Continue switch (overlay recipe; no fake 2G YAML), per-band pass_mode, Schmitt VT chips, PSU_MSO hide Freq/Amp. STS PDF Pass criteria / How met from min/max/value -- never invent. Dual Excel + sessions/csv + path_b_write.json stay.
- JH room 2026-09-18 numbers gate: copy grounded vcc_grid CONFIRMED (band/fixed VIH/VIL + G14 VT+/-) from box SoT / signed cards into ate part yaml. check_logic_dc REQUIRES CONFIRMED vcc_grid (unlocks threshold numbers). Keep fail-closed: stable_eps_A null, retention MAX if missing, RS164 Ioff+ICCT ABSENT (delta_icc off), G07 VOH N_A, glyph-missing uA/mA (G07 vol_table stays 4 rows). Spot-check G08 card bands and G14 VT+/- vs yaml; if a row is not on the signed card, leave UNSURE -- do not invent. Do not copy SoT excel_plots onto 08/07. Do not copy SoT G07 100uA/24mA onto vol_table.
- STS latest PDF: after Version run, `export_latest_report` overwrites `{Version}/report.pdf` from session rows (pass/fail vs limits). Existing sessions/datalog.* stay. Never invent pass numbers.
- Dual-channel Continue for future 2Gxx: `recipe.dual_channel_continue` + `recipe.channels` as DATA (OpAmp CHA then CHB Continue reused, not hardcoded). Path B registry stays dual_channel=False. No fake rs2g YAML without Datasheet card. See docs/LOGIC_DC_DUAL_CHANNEL.md.
- CSV: `write_path_b_csv` `sessions/csv/{sheet}.csv` + `path_b_write.json` overwrite with golden_auto; `write_datapoints_csv` sidecar `*_datapoints.csv` beside the xlsx (full data.rows). pretty / ultimate never auto (no auto CSV there).
- Path B Excel lock: never `_filled.xlsx`. PermissionError is OrphanWorkbook FAIL (no second path). rs1g08 without excel_plots stays paste.values. Fill Excel Path B must create the first book (do not return no_workbook first). Series ids only from ALLOWED_SERIES; Schmitt uses vtplus/vtminus not VIH/VIL; ioz only if OE; delta_icc only if enabled+mapped.
- Path B Excel split: auto/golden_auto = chosen Version workbook/ (one_per_version_overwrite). pretty/ultimate_manual = jot (never_auto_write; pretty never auto). Continue/Open Session/START bind fill/plot to golden_auto only. FAIL if auto dest == pretty/ultimate, or a second golden Version xlsx, or invented columns (G16/GBW). Jot/pretty next to golden is not an orphan. Identify jot by filename/folder regex (ultimate/jot/pretty/all-test) -- do not invent a data_paths.ultimate key. product_model.workbook_policy is a nested map, not a string. Do not import excel_lock from product_model (circular).
- Dual Excel CSV: sessions/csv/{sheet}.csv + sessions/path_b_write.json overwrite with golden_auto only. pretty never auto (xlsx or CSV). Optional data_paths.csv in DATA_PATH_TEMPLATES requires 97/126/34 yaml keys (handoff exact-match). 08/07 excel_lock OFF until signed (sheet_map).
- RS1G08 / RS1G07 extract honesty: do not invent VIH/VIL from 9.1 PDF images. Do not copy extract 9.2 over Ariff 08 voh_table. 07 open-drain: no VOH, no ioz (Y=Z is not OE). Light-load 100uA and IOL 24mA VCC glyph-missing -- omit. 07 vol_table is 4 extract-explicit IOL rows. Do not call _fail_closed_until_signed on unsigned 08/07 (would red the check).

## cite

ate/tests/logic/excel_lock.py
ate/tests/logic/logic_dc.py
ate/tests/logic/threshold_search.py
ate/tests/logic/product_model.py
ate/tests/logic/seelim_dc.py
ate/core/check_logic_dc.py
ate/core/check_add_test.py
docs/LOGIC_DC.md
docs/LOGIC_DC_OPERATOR.md
docs/datasheet/card_fields.schema.yaml
ate/ui/web/index.html
ate/config/parts/rs1g97.yaml
ate/config/parts/rs1g126.yaml
ate/config/parts/rs1gt34.yaml
ate/config/parts/rs1g08.yaml
ate/config/parts/rs1g07.yaml
ate/config/limits/rs1g07.yaml
ate/tests/logic/wraps.py
ate/core/runner.py
