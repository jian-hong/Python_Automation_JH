# EPIC-A01 Mode B completeness (code + RPC)

keywords: epic-a01, mode-b, family-rail, set_family, load_family, completeness
main_idea: EPIC-A01 acceptance holds on live worker: Logic clears OPA tests/fixtures; OpAmp restores 16 tests + gain catalog; START stays session-gated; category-first loop intact. Epic closed/accepted 2026-08-19.

## Assertion checked

WHEN operator selects Logic, no OpAmp-only fixture gain boards and only that family's tests (empty OK). WHEN OpAmp, restore OPA tests + fixture catalog without regressing category-first or START session lock.

## Commands / RPC

```text
cd /d C:\Users\OoiJianHong\EUGENE~1\PYTHON~1
venv\Scripts\python.exe -m ate.core.check_family_load
# OK opamp=16 tests logic=0 tests (no OPA leak after switch)

POST http://127.0.0.1:8766
set_family {logic} -> family=logic test_count=0; list_tests=[]; list_fixture_modes=[]
set_family {opamp} -> family=opamp test_count=16; fixtures BUFFER,G11,G_NEG100,ATE,G201,G1001
session_status -> open=false busy=false (idle)
```

## Code anchors

- `ate/core/registry.py` `load_family` clear+import `FAMILY_PACKAGES`
- `ate/core/runner.py` `load_family`; run loop category -> channel -> DUT
- `ate/worker/server.py` `get_family` / `set_family`; `list_fixture_modes` empty if family != opamp
- `ate/ui/web/index.html` `.family-rail` vs decorative `.logo`; `#btn-start` disabled
- `ate/ui/web/app.js` rail -> `set_family`; hide `#panel-gain-boards` when not opamp; START `!sessionOpen`

## Verdict

COMPLETE. Recommend new epic-agent Mode A for EPIC-A02 slice only.
