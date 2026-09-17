# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g126, ioz, schmitt, UNCONFIRMED, pass_mode, test_params, logic_inputs, eugene-console, seelim

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run. Isolation is derived from truth_table (Y tracks swept pin; invert only if no track combo -- See Lim algorithm, not per-SKU hardcodes). ICC corners = 2^n. Version overlay `_manifest/test_params.yaml`. pass_mode first-class (range / min-only / max-only / fail-open / unspec). RS1G97 / RS1G126 truth_table + isolation are CONFIRMED (Jian Hong 2026-09-17). C-track A:H B:L is unlocked at run. STANDARD FORMAT checklist is `#add-test-format` on Setup Test program (Path A/B/C). `#panel-logic-dc` visualises enabled tests, recipe, truth table, isolation, ICC corners, limits+pass_mode. Add SKU: `docs/LOGIC_DC.md`. Operator bench: `docs/LOGIC_DC_OPERATOR.md` (DEMO/SIM is not a reproduce; Excel cells only from sheet_map / campaign_outline). See Lim wrap is `seelim_dc.py` locator only.

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
- Never reuse stable_eps_V as amps. Current settle uses stable_eps_A only; 97/126 default null (FAIL-closed). Do not invent a uA epsilon. Overlay/panel grounds it.
- Operator Excel: never invent cells. Fill Excel = campaign sheet_map paste.values; known Logic VOX/ICC cells only from campaign_outline.py when those sheets exist.

## cite

ate/tests/logic/logic_dc.py
ate/tests/logic/product_model.py
ate/tests/logic/seelim_dc.py
ate/core/check_logic_dc.py
ate/core/check_add_test.py
docs/LOGIC_DC.md
docs/LOGIC_DC_OPERATOR.md
ate/ui/web/index.html
ate/config/parts/rs1g97.yaml
