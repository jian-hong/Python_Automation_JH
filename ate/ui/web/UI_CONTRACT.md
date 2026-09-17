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
11. Results `#btn-export-datalog` writes STS `sessions/datalog.md|.html|.pdf`. `#btn-fetch-datasheet` fills `ate/config/limits/<part>.yaml` from local Reference PDFs first (en.run-ic.com only if unfound). `#btn-fill-excel` writes `paste.values` numbers from living `report.json` (DUT list or CHA/CHB grid).
12. Setup `#panel-logic-dc` (Logic family Path B) shows editable `truth_table`, `isolation`, `pass_mode`, `vcc_list`, and `gaps` plus visual recipe tables (ICC 2^n, derived isolation, limits + `pass_mode`). Hidden when the part has no `product_model`. `#btn-save-logic-dc` writes part yaml. `#btn-save-test-params` writes campaign `_manifest/test_params.yaml`. UNCONFIRMED status is not greenable. Results table includes Mode. No extra tab.

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
