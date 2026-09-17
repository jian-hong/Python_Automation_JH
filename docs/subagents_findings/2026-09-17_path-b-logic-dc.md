# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g126, ioz, schmitt, UNCONFIRMED, pass_mode, test_params, logic_inputs, eugene-console, seelim

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run. Isolation is derived from truth_table (Y tracks swept pin; invert only if no track combo -- See Lim algorithm, not per-SKU hardcodes). ICC corners = 2^n. Version overlay `_manifest/test_params.yaml`. pass_mode first-class (range / min-only / max-only / fail-open / unspec). RS1G97 / RS1G126 truth_table + isolation are CONFIRMED (Jian Hong 2026-09-17). C-track A:H B:L is unlocked at run. STANDARD FORMAT checklist is `#add-test-format` on Setup Test program (Path A/B/C). `#panel-logic-dc` visualises enabled tests, recipe, card_fields (OOP assign/edit/delete including wire_map / settle_prompt / data_paths), truth table, isolation, ICC corners, limits+pass_mode. Add SKU: `docs/LOGIC_DC.md`. Operator bench: `docs/LOGIC_DC_OPERATOR.md` (DEMO/SIM is not a reproduce; Excel cells only from sheet_map / campaign_outline). See Lim wrap is `seelim_dc.py` locator only. OOP schema: `docs/datasheet/card_fields.schema.yaml`. Runnable lock: every enabled_tests id must have TestSpec.run callable. AE/FAE Continue: wire_map from CONFIRMED pins+pin_drive only (never invent nets); settle_prompt show wait; data_paths folder templates; FAIL attach `{test}/DUT_n/`.

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
- Operator Excel: never invent cells. Fill Excel = campaign sheet_map paste.values; known Logic VOX/ICC cells only from campaign_outline.py when those sheets exist.
- AE/FAE wire_map only from CONFIRMED pins + pin_drive. PSU CH2 is pin Y use=load (existing VOH/VOL fixture), not a new net. SCOPE CH1 is output_pin Y (debug capture), not IN+/VOUT. check_logic_dc FAIL-closes empty wire_map / missing data_paths on 97/126 only (not rs1g08).
- runner pause_hook must accept checklist= so Logic Continue is not OpAmp IN+/VOUT. Do not wrap TestSpec.run at _register (th.run is ldc._run_input_threshold).

## cite

ate/tests/logic/logic_dc.py
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
ate/tests/logic/wraps.py
ate/core/runner.py
