# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g126, ioz, schmitt, eugene-console

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run; they differ by truth table, isolation, pin roles, limits, and recipe. Isolation is YAML (RS1G97 HOLD CONFIRM) or derived from truth_table. No per-part Python ifs. OE optional: IOZ only when oe != none (RS1G126 keeps ioz; 97/08 do not). voh/vol/icc registry ids dispatch to Path B when a model exists, else RS0204 dual-rail. See Lim goldens are not the runtime.

## traps

- Logic registry is one id namespace: do not register a second `voh`/`vol`/`icc`. Dispatch on product_model vs vcca/vccb.
- Do not invent truth rows or VOH/VOL numbers. 97 truth table is HOLD CONFIRM (OCR garbled; matches isolation mux). VOH/VOL for 97/126 stay PROVISIONAL (no rows in existing limits yaml).
- 126 unused data ties are UNSURE; only OE-active isolation for A.
- ten/tdis stay AC on 126.
- Single-rail parts must not inherit RS0204 `vccb` from LOGIC_TEST_DEFAULTS.

## cite

ate/tests/logic/logic_dc.py
ate/tests/logic/product_model.py
ate/core/check_logic_dc.py
