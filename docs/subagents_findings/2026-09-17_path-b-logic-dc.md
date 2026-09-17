# Path B Logic DC (shared runner)

Date: 2026-09-17
Keywords: path-b, logic-dc, product_model, isolation, rs1g97, rs1g08, rs1g126, ioz, schmitt, eugene-console, seelim, goldens, pass_mode

## main_idea

One shared Logic DC runner (`ate/tests/logic/logic_dc.py`) driven by `product_model` YAML. 2-input AND (RS1G08) and 3-input RS1G97 share the same TestSpec.run; they differ by truth table, isolation, pin roles, limits, and recipe. RS1G97 truth table is the in-repo datasheet extract (C=L => Y=B; C=H => Y=A AND B), not a C-select MUX. Isolation is YAML or derived from truth_table. No per-part Python ifs. OE optional: IOZ only when oe != none. See Lim wrap is `ate/tests/logic/seelim_dc.py` locator: `goldens/see_lin/<PART>/current_tests.py` then Downloads\\See Lim Repo. It is not the START runtime and must not copy limits. Colleague trees (Ariff / See Lim / Eugene) are detect-only. `pass_mode` on existing limits yaml (range / max-only).

## traps

- Logic registry is one id namespace: do not register a second `voh`/`vol`/`icc`. Dispatch on product_model vs vcca/vccb.
- Do not scrape Ariff/See Lim/Eugene trees into YAML. Limits stay in `ate/config/limits/` citing the Reference PDF extract.
- Do not invent VOH/VOL load rows. 97/126 VOH stay PROVISIONAL without a part `voh_table`.
- 126 unused data ties are UNSURE; only OE-active isolation for A.
- ten/tdis stay AC on 126.
- PSU CH2 is Y-load/vref; RS1G97 pin C is PSU CH3.
- Single-rail parts must not inherit RS0204 `vccb` from LOGIC_TEST_DEFAULTS.
- Do not touch family_ingest / extra_families / registry FAMILY_PACKAGES.

## cite

ate/tests/logic/logic_dc.py
ate/tests/logic/product_model.py
ate/tests/logic/seelim_dc.py
ate/core/check_logic_dc.py
