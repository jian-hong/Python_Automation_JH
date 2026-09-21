"""Fail-closed UI contract for ate/ui/web (A17-T02).

Run: python -m ate.core.check_ui_contract
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "ui" / "web"
INDEX = WEB / "index.html"


def main() -> int:
    errors: list[str] = []
    if not INDEX.is_file():
        print("FAIL check_ui_contract: index.html missing")
        return 1
    html = INDEX.read_text(encoding="utf-8")

    tabs = re.findall(r'data-page="([a-z0-9\-]+)"', html)
    if not tabs:
        errors.append("no data-page tabs found")
    for name in tabs:
        if f'id="page-{name}"' not in html:
            errors.append(f"tab data-page={name!r} missing section#page-{name}")

    nav_count = len(re.findall(r'<nav\s+class="[^"]*\btabs\b', html))
    if nav_count != 1:
        errors.append(f"expected exactly 1 nav.tabs, found {nav_count}")

    # Google Fonts families: count family= tokens only
    families: list[str] = []
    for m in re.finditer(r"family=([A-Za-z0-9+]+)", html):
        fam = m.group(1).replace("+", " ")
        if fam and fam not in families:
            families.append(fam)
    if len(families) > 3:
        errors.append(f"too many webfont families ({len(families)}): {families}")

    if "UI_CONTRACT.md" not in (WEB / "UI_CONTRACT.md").name or not (WEB / "UI_CONTRACT.md").is_file():
        errors.append("ate/ui/web/UI_CONTRACT.md missing")
    agents = Path(__file__).resolve().parents[2] / "AGENTS.md"
    if not agents.is_file():
        errors.append("repo AGENTS.md missing")

    if "tags" not in tabs:
        errors.append("Tags tab (data-page=tags) missing")
    if 'data-family="power"' not in html:
        errors.append("Power family rail button missing")
    if 'id="setup-label-chips"' not in html or 'id="btn-setup-add-label"' not in html:
        errors.append("Setup Add labels control missing")
    if 'id="btn-add-version"' in html:
        errors.append("+ Version extra button must not exist; Version box is editable")
    if 'id="setup-label-new"' in html:
        errors.append("Or type extra field must not exist; label value is editable")
    if 'class="combo"' not in html or "combo-caret" not in html:
        errors.append("Setup combo dropdown (caret + open list) missing")
    if 'id="db-tag-input"' not in html:
        errors.append("Setup tag type field missing")
    if 'id="db-version-list"' in html or 'id="setup-label-value-list"' in html:
        errors.append("datalist leftover; Setup uses .combo menu not datalist")
    if 'id="run-ledger"' not in html or 'id="btn-open-central"' not in html:
        errors.append("Run ledger / Open central DB missing")
    if "sharepoint" not in html.lower():
        errors.append("Setup central-db hint must mention SharePoint")
    if 'id="pin1-hint"' not in html:
        errors.append("pin-1 orientation hint missing")
    if 'id="btn-tags-clear"' not in html:
        errors.append("Clear all tags control missing")
    if 'id="label-scope"' not in html:
        errors.append("Label scope (campaign / class / all) missing")
    if 'id="btn-save-person"' not in html or 'id="btn-forget-person"' not in html:
        errors.append("Save / Forget person controls missing")
    if 'id="btn-export-datalog"' not in html or 'id="btn-fetch-datasheet"' not in html:
        errors.append("STS datalog export / datasheet fetch controls missing")
    if 'id="btn-fill-excel"' not in html:
        errors.append("Fill Excel numbers control missing")
    if 'id="panel-logic-dc"' not in html or 'id="logic-dc-truth"' not in html:
        errors.append("Logic DC product_model panel missing")
    if 'id="logic-dc-isolation"' not in html or 'id="logic-dc-pass-mode"' not in html:
        errors.append("Logic DC isolation/pass_mode editors missing")
    if 'id="logic-dc-vcc-list"' not in html or 'id="logic-dc-gaps"' not in html:
        errors.append("Logic DC vcc_list/gaps fields missing")
    if 'id="btn-save-logic-dc"' not in html:
        errors.append("Logic DC save control missing")
    if 'id="btn-save-test-params"' not in html or 'id="logic-dc-body"' not in html:
        errors.append("Logic DC recipe panel / Save Version overlay missing")
    if 'id="add-test-format"' not in html or "STANDARD FORMAT" not in html:
        errors.append("STANDARD FORMAT checklist (#add-test-format) missing")
    if 'id="btn-save-pass-mode"' not in html:
        errors.append("Test program Save pass_mode overlay missing")
    tp_at = html.find("<h2>Test program</h2>")
    fmt_at = html.find('id="add-test-format"')
    if tp_at < 0 or fmt_at < 0 or not (tp_at < fmt_at < tp_at + 4000):
        errors.append("STANDARD FORMAT checklist must live on Test program (always visible)")

    js_path = WEB / "app.js"
    if not js_path.is_file():
        errors.append("app.js missing")
    else:
        js = js_path.read_text(encoding="utf-8")
        if re.search(r"\bif\s+![A-Za-z_]", js):
            errors.append("app.js has invalid if ! without parentheses")
        if "inventoryRows" not in js or "loadInventory" not in js:
            errors.append("Setup tracking sheet must load inventory")
        if "loadLogicDcPanel" not in js or "get_product_model" not in js:
            errors.append("Logic DC panel must load get_product_model")
        if "save_product_model" not in js or "saveLogicDcPanel" not in js:
            errors.append("Logic DC panel must save product_model")
        if "renderLogicDc" not in js or "save_test_params" not in js or "pass_mode" not in js:
            errors.append("Logic DC recipe panel / pass_mode visualisation missing")
        if "test-pass-mode" not in js or "passModeSelect" not in js or "fail-open" not in js:
            errors.append("Test program pass_mode selects missing")
        if "icc_corner_rows" not in js or "Enabled tests" not in js:
            errors.append("Logic DC panel must visualise enabled tests and ICC corners")
        if "saveTestParamsOverlay" not in js or "btn-save-pass-mode" not in js:
            errors.append("Test program / Logic DC must share saveTestParamsOverlay")
        if "wirePassModeSync" not in js:
            errors.append("pass_mode selects must sync Test program and Logic DC")
        if "!(inventoryRows || []).length" not in js:
            errors.append("family rail click must retry loadInventory when tracking rows are empty")
        combo = re.search(
            r'\["db-component", "db-part", "db-package", "db-operator", "db-version"\]\.forEach[\s\S]*?\$\("btn-apply-db"\)',
            js,
        )
        if not combo:
            errors.append("Setup campaign combo change listener missing")
        elif "applyDb(" in combo.group(0):
            errors.append("Setup combo change must not auto applyDb")

    if errors:
        print("FAIL check_ui_contract:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK check_ui_contract tabs={tabs} fonts={families}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
