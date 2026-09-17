# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g126, ioz, schmitt, UNCONFIRMED, pass_mode, test_params, logic_inputs, eugene-console, seelim

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run. Isolation is derived from truth_table (Y tracks swept pin; invert only if no track combo -- See Lim algorithm, not per-SKU hardcodes). ICC corners = 2^n. Version overlay `_manifest/test_params.yaml`. pass_mode first-class. RS1G97 truth_table is Datasheet §4 FUNCTION TABLE rows with status UNCONFIRMED (not Datasheet-signed, not greenable). C invert A:L B:H is the run fallback; C-track A:H B:L is PROPOSED HOLD CONFIRM. Setup panel `#panel-logic-dc` edits truth_table/isolation/pass_mode/vcc_list/gaps and visualises recipe. Add SKU: `docs/LOGIC_DC.md`. See Lim wrap is `seelim_dc.py` locator only.

## traps

- Logic registry is one id namespace: do not register a second `voh`/`vol`/`icc`. Dispatch on product_model vs vcca/vccb.
- Do not invent truth rows or VOH/VOL IOH/IOL numbers. 97 table is UNCONFIRMED. VOH/VOL for 97/126 stay PROVISIONAL.
- check_logic_dc is FAIL-CLOSED while 97 or 126 is UNCONFIRMED. Do not print OK / claim green.
- 126 unused data ties and truth_table.status are UNCONFIRMED (not from_datasheet_function_table). Only OE-active isolation for A.
- Do not scrape Ariff/See Lim/Eugene trees into YAML. Limits stay in `ate/config/limits/` citing the Reference PDF extract.
- ten/tdis stay AC on 126.
- PSU CH2 is Y-load/vref; RS1G97 pin C is PSU CH3 (PROVISIONAL fixture map).
- Single-rail parts must not inherit RS0204 `vccb` from LOGIC_TEST_DEFAULTS.
- vcc_op_min/max are range metadata, not a sweep. Do not expand vcc_list.
- Do not touch family_ingest / extra_families / registry FAMILY_PACKAGES.
- IOZ/IOFF only when oe != none.

## cite

ate/tests/logic/logic_dc.py
ate/tests/logic/product_model.py
ate/tests/logic/seelim_dc.py
ate/core/check_logic_dc.py
ate/core/check_add_test.py
docs/LOGIC_DC.md
ate/ui/web/index.html
ate/config/parts/rs1g97.yaml
