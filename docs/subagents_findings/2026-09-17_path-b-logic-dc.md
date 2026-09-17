# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g126, ioz, schmitt, UNCONFIRMED, pass_mode, eugene-console, seelim

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run. RS1G97 truth_table is Datasheet §4 FUNCTION TABLE rows with status UNCONFIRMED (not Datasheet-signed, not greenable). Isolation is derived from that table. pass_mode (alias limit_mode): Schmitt VT+/VT- = range; plain VIH=min_only, VIL=max_only (126 is not collapsed to input_threshold:range). Setup panel `#panel-logic-dc` edits truth_table/isolation/pass_mode/vcc_list/gaps. INSTRUMENT_SENSE: ICC DMM-on-VCC; VOH/VOL/IOZ force/sense. See Lim wrap is `seelim_dc.py` locator only, not START runtime.

## traps

- Logic registry is one id namespace: do not register a second `voh`/`vol`/`icc`. Dispatch on product_model vs vcca/vccb.
- Do not invent truth rows or VOH/VOL IOH/IOL numbers. 97 table is UNCONFIRMED. VOH/VOL for 97/126 stay PROVISIONAL.
- check_logic_dc is FAIL-CLOSED while 97 or 126 is UNCONFIRMED. Do not print OK / claim green.
- 126 unused data ties and truth_table.status are UNCONFIRMED (not from_datasheet_function_table). Only OE-active isolation for A.
- ten/tdis stay AC on 126.
- PSU CH2 is Y-load/vref; RS1G97 pin C is PSU CH3 (PROVISIONAL fixture map).
- Single-rail parts must not inherit RS0204 `vccb` from LOGIC_TEST_DEFAULTS.
- vcc_op_min/max are range metadata, not a sweep. Do not expand vcc_list.
- Do not scrape Ariff/See Lim/Eugene trees into YAML.

## cite

ate/tests/logic/logic_dc.py
ate/tests/logic/product_model.py
ate/tests/logic/seelim_dc.py
ate/core/check_logic_dc.py
ate/ui/web/index.html
ate/config/parts/rs1g97.yaml
