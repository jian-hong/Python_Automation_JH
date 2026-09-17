# Operator UI contract (ate/ui/web)

AI and humans must keep the console shape stable.

## Add a page

1. Add `<button class="tab" data-page="{name}">` inside the single `nav.tabs.glass`.
2. Add `<section id="page-{name}" class="page">` inside `main`.
3. Reuse `glass panel`, `db-grid`, `btn`, `btn accent`, `btn ghost`, `hint`, `row`.
4. Bump `styles.css?v=` cache query in `index.html`.
5. Wire clicks in `app.js` only (no second framework).
6. Setup Component/Part/Package/Operator/Version/Kind/Value/Scope use `.combo` (caret + body `#ate-combo-menu`). Do not bring back `<datalist>`.
7. Tags: `#db-tag-input` Space/Enter adds; chips compact with `+N more` then expand. `#btn-tags-clear` empties campaign tags. `#label-scope` is this campaign / this class / all products.
8. Results `#run-ledger` lists session JSON from the central `#Test_Database`. No extra tab.
9. Setup `#btn-open-central` opens the SharePoint-synced folder, or the `sharepoint.url` https if that folder is missing. It must not mkdir a private `#Test_Database`.
10. Setup `#pin1-hint` is the DUT orientation gate reminder (Abort if pin-1 is wrong).
11. Results `#btn-export-datalog` writes STS `sessions/datalog.md|.html|.pdf`. `#btn-fetch-datasheet` fills `ate/config/limits/<part>.yaml` from local Reference PDFs first (en.run-ic.com only if unfound). `#btn-fill-excel` writes `paste.values` numbers from living `report.json` (DUT list or CHA/CHB grid) for mapped/OpAmp books; Path B Logic DC overwrites the Version **golden_auto** xlsx (`workbook_policy.golden_auto: one_per_version_overwrite`) and never the **ultimate_manual** jot book.
12. Setup `#add-test-format` (always visible on Test program) is the STANDARD FORMAT checklist (Path A Test program / Path B Logic DC recipe / Path C Detected tests -> Wrap + enable on part). `#panel-logic-dc` shows Customise Parameters (`vcc_grid` FIXED POINTS chips + RANGE SWEEPS, merged `vcc_list` preview, stimulus PSU_MSO vs AWG; PSU_MSO hides Freq/Amp), enabled tests, recipe (`logic_inputs`, `vcc_list`, `stable_eps_A`, n), per-field card editors from `docs/datasheet/card_fields.schema.yaml` (assign/edit/delete), truth table, isolation including PROPOSED/HOLD, ICC 2^n corners, and limits + `pass_mode`. Hidden when the part has no `product_model`. Test program `#test-list` `.test-pass-mode` is per-spec editable (range / min-only / max-only / fail-open / unspec). `#btn-save-pass-mode` and `#btn-save-test-params` write campaign `_manifest/test_params.yaml` only (vcc_grid + merged vcc_list + pass_mode + sample_size). `#btn-save-logic-dc` writes part yaml via card_fields keys. UNCONFIRMED status is not greenable. Results table includes Mode. No extra tab. No xyflow.

## Forbidden

- Second `nav.tabs` (or a parallel top nav)
- Fourth webfont family (keep Barlow / JetBrains Mono / Space Grotesk)
- New design system / CSS reset
- Dumping large inline `style=` blocks for layout (small flex tweaks OK)
- Editing this tree from a regex "auto-improve UI" pass without running `python -m ate.core.check_ui_contract`

## Check

```
python -m ate.core.check_ui_contract
```

Fails if any `data-page` lacks `#page-*`, or if more than one `.tabs` nav, or if a fourth Google Fonts family appears.
